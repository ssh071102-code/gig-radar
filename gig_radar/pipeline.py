import logging
from gig_radar.normalize import raw_to_lead
from gig_radar.store import LeadStore
from gig_radar.brain.triage import triage as _real_triage
from gig_radar.brain.draft import draft_lead as _real_draft
from gig_radar.push.telegram import push_digest as _real_push

log = logging.getLogger("gig_radar")


def ingest(adapters, store: LeadStore):
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


def run_pipeline(adapters, store, positioning, llm, triage_model, draft_model,
                 top_n, min_score, telegram, dry_run=False, enrich=True,
                 _triage=_real_triage, _draft=_real_draft, _push=_real_push):
    """Full pipeline: 1) fetch 2) dedup 3) score -> top N above threshold -> 4) draft
    -> 5) push -> 6) write back.
    Failures are never dropped silently: unscored leads are not persisted (retried next
    run); leads whose push fails are not marked pushed.
    dry-run has no persistence side effects (a clean preview)."""
    fresh, errors = ingest(adapters, store)
    scored = _triage(fresh, positioning, llm, triage_model)
    n_unscored = sum(1 for l in scored if l.status == "unscored")
    log.info("ingested %d fresh; scored %d; unscored %d (retry next run); source errors=%s",
             len(fresh), len(scored) - n_unscored, n_unscored, errors)

    top = [l for l in scored if l.score is not None and l.score >= min_score][:top_n]
    for lead in top:
        _draft(lead, positioning, llm, draft_model, enrich)

    token, chat_id = telegram
    pushed = []
    if dry_run:
        for lead in top:
            log.info("[dry-run] would push: %s (%s)", lead.title, lead.score)
        # No persistence: dry-run stays a clean preview and never pollutes a later real run.
    else:
        # Only persist leads that scored successfully (unscored ones are retried next
        # run, never dropped silently).
        for l in scored:
            if l.status == "scored":
                store.upsert(l)
        pushed = _push(top, token, chat_id)         # returns the leads pushed successfully
        for lead in pushed:
            store.mark(lead.id, "pushed")

    return {"fresh": len(fresh), "scored": len(scored) - n_unscored,
            "unscored": n_unscored, "drafted": len(top),
            "pushed": len(pushed), "errors": errors}
