import logging
from datetime import UTC, datetime, timedelta

from gig_radar.adapters.base import SourceAdapter
from gig_radar.brain.draft import draft_lead as _real_draft
from gig_radar.brain.triage import triage as _real_triage
from gig_radar.llm import SupportsComplete
from gig_radar.models import Lead
from gig_radar.normalize import raw_to_lead
from gig_radar.push.telegram import TelegramTarget
from gig_radar.push.telegram import push_digest as _real_push
from gig_radar.store import LeadStore

log = logging.getLogger("gig_radar")


def ingest(adapters: list[SourceAdapter],
           store: LeadStore) -> tuple[list[Lead], dict[str, str]]:
    """Steps 1-2: fetch and normalize/dedup. Nothing is persisted here -- persistence
    happens in run_pipeline once a lead is processed successfully, so a failed lead is
    never mistakenly marked as seen. Returns (fresh_leads, errors).
    Per-source failures are isolated: record the error and keep going with the other
    sources instead of raising."""
    all_leads = []
    errors: dict[str, str] = {}
    for ad in adapters:
        try:
            raws = ad.fetch()
        except Exception as e:                     # noqa: BLE001 isolate source failures
            errors[ad.name] = repr(e)
            log.warning("source %s failed: %r", ad.name, e)
            continue
        all_leads.extend(raw_to_lead(r) for r in raws)
    # Nothing is persisted here -- run_pipeline persists after successful processing,
    # so a failed lead is never mistakenly marked as seen.
    return store.filter_unseen(all_leads), errors


def _is_stale(lead: Lead, cutoff: datetime | None) -> bool:
    """True if the lead was posted (or, lacking a post date, first fetched) before cutoff."""
    ts = lead.posted_at or lead.fetched_at
    if cutoff is None or ts is None:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts < cutoff


def run_pipeline(adapters: list[SourceAdapter], store: LeadStore, positioning: str,
                 llm: SupportsComplete, triage_model: str, draft_model: str,
                 top_n: int, min_score: int, telegram: TelegramTarget,
                 dry_run: bool = False, enrich: bool = True, persona: dict | None = None,
                 max_age_days: int | None = 14, max_draft_attempts: int = 3,
                 _triage=_real_triage, _draft=_real_draft, _push=_real_push) -> dict:
    """Full pipeline: 1) fetch 2) dedup 3) score -> top N above threshold -> 4) draft
    -> 5) push -> 6) write back.

    Failures are never dropped silently: unscored leads are not persisted (retried next
    run); a lead whose draft fails is not pushed and stays in the backlog, until it has
    failed `max_draft_attempts` times and is marked "failed"; leads whose push fails are
    not marked pushed. Leads older than `max_age_days` (by post date, else first fetch)
    are marked "expired" and never pushed; None or 0 disables the age limit.
    dry-run has no persistence side effects (a clean preview).

    `telegram` is a TelegramTarget (or any (token, chat_id) tuple). The `_triage`,
    `_draft` and `_push` keywords are the pipeline's step dependencies: they default to
    the real implementations and exist so tests and the demo command can substitute
    deterministic steps without patching."""
    fresh, errors = ingest(adapters, store)
    scored = _triage(fresh, positioning, llm, triage_model, persona=persona)
    n_unscored = sum(1 for lead in scored if lead.status == "unscored")
    log.info("ingested %d fresh; scored %d; unscored %d (retry next run); source errors=%s",
             len(fresh), len(scored) - n_unscored, n_unscored, errors)

    # Push candidates come from the union of this run's scored leads and the store's
    # backlog of scored-but-never-pushed leads. Without the backlog, a lead that clears
    # min_score on a busy day but misses the top_n cutoff would be persisted as seen
    # and then silently lost forever -- it surfaces on the next quieter run instead.
    pool = {lead.id: lead for lead in store.by_status("scored")}
    for lead in scored:
        if lead.status == "scored":
            pool[lead.id] = lead

    cutoff = datetime.now(UTC) - timedelta(days=max_age_days) if max_age_days else None
    expired = [lead for lead in pool.values() if _is_stale(lead, cutoff)]
    for lead in expired:
        lead.status = "expired"

    eligible = sorted(
        (lead for lead in pool.values()
         if lead.status == "scored" and lead.score is not None and lead.score >= min_score),
        key=lambda lead: lead.score, reverse=True)
    top = eligible[:top_n]
    drafted, draft_failed = [], []
    for lead in top:
        _draft(lead, positioning, llm, draft_model, enrich, persona=persona)
        if lead.draft:
            lead.draft_failures = 0
            drafted.append(lead)
            continue
        lead.draft_failures += 1
        if lead.draft_failures >= max_draft_attempts:
            lead.status = "failed"
        draft_failed.append(lead)
        log.warning("draft failed for %s (attempt %d/%d)%s", lead.id, lead.draft_failures,
                    max_draft_attempts, "; giving up" if lead.status == "failed" else "")

    token, chat_id = telegram
    pushed = []
    if dry_run:
        for lead in drafted:
            log.info("[dry-run] would push: %s (%s)", lead.title, lead.score)
        # No persistence: dry-run stays a clean preview and never pollutes a later real run.
    else:
        # Persist every lead whose state changed this run. Unscored leads are skipped on
        # purpose: they are retried next run, never dropped silently.
        changed = {lead.id: lead for lead in scored if lead.status != "unscored"}
        changed.update((lead.id, lead) for lead in (*top, *expired))
        for lead in changed.values():
            store.upsert(lead)
        pushed = _push(drafted, token, chat_id)     # returns the leads pushed successfully
        for lead in pushed:
            store.mark(lead.id, "pushed")

    return {"fresh": len(fresh), "scored": len(scored) - n_unscored,
            "unscored": n_unscored, "drafted": len(drafted),
            "draft_failed": len(draft_failed), "expired": len(expired),
            "pushed": len(pushed), "errors": errors}
