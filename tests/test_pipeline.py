from gig_radar.config import load_config
from gig_radar.models import RawItem
from gig_radar.pipeline import ingest, run_pipeline
from gig_radar.store import LeadStore


def test_load_config(tmp_path):
    (tmp_path / "settings.yaml").write_text("top_n: 5\nmin_score_to_push: 60\n", encoding="utf-8")
    (tmp_path / "sources.yaml").write_text("reddit:\n  enabled: false\n", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.settings["top_n"] == 5
    assert cfg.sources["reddit"]["enabled"] is False


class OkAdapter:
    name = "ok"

    def fetch(self):
        return [RawItem(source="rss", external_id="1", url="http://x",
                        title="AI job", raw_text="b")]


class BoomAdapter:
    name = "boom"

    def fetch(self):
        raise RuntimeError("source down")


def _scoring_triage(score):
    def fake_triage(leads, positioning, llm, model, persona=None):
        for lead in leads:
            lead.score = score
            lead.status = "scored"
            lead.channel_action = "comment"
        return leads
    return fake_triage


def fake_draft(lead, positioning, llm, model, enrich, persona=None):
    lead.draft = "d"
    return lead


def test_ingest_isolates_failing_source(tmp_path):
    store = LeadStore(tmp_path / "db.sqlite")
    leads, errors = ingest([OkAdapter(), BoomAdapter()], store)
    assert len(leads) == 1                              # the ok source succeeds, boom is isolated
    assert leads[0].id.startswith("rss:")
    assert "boom" in errors and "source down" in errors["boom"]


def test_ingest_dedups_across_runs(tmp_path):
    store = LeadStore(tmp_path / "db.sqlite")
    first, _ = ingest([OkAdapter()], store)
    assert len(first) == 1
    for lead in first:
        store.upsert(lead)                       # simulate run_pipeline persisting after success
    second, _ = ingest([OkAdapter()], store)     # same source runs again
    assert len(second) == 0                      # already persisted, deduped


def test_run_pipeline_dry_run_pushes_nothing(tmp_path):
    calls = {"push": 0}

    def fake_push(leads, token, chat_id):
        calls["push"] += len(leads)
        return list(leads)

    store = LeadStore(tmp_path / "db.sqlite")
    result = run_pipeline(
        adapters=[OkAdapter()], store=store, positioning="POS", llm=None,
        triage_model="t", draft_model="d", top_n=5, min_score=55,
        telegram=("TOK", "42"), dry_run=True, enrich=False,
        _triage=_scoring_triage(90), _draft=fake_draft, _push=fake_push,
    )
    assert calls["push"] == 0                 # dry-run never pushes
    assert result["scored"] == 1 and result["drafted"] == 1
    assert store.all() == []                  # dry-run has no persistence side effects


def test_run_pipeline_real_push_marks_pushed(tmp_path):
    pushed = []

    def fake_push(leads, token, chat_id):
        pushed.extend(leads)
        return list(leads)

    store = LeadStore(tmp_path / "db.sqlite")
    run_pipeline(adapters=[OkAdapter()], store=store, positioning="POS", llm=None,
                 triage_model="t", draft_model="d", top_n=5, min_score=55,
                 telegram=("TOK", "42"), dry_run=False, enrich=False,
                 _triage=_scoring_triage(90), _draft=fake_draft, _push=fake_push)
    assert len(pushed) == 1
    assert store.get(pushed[0].id).status == "pushed"    # status written back


def test_run_pipeline_unscored_not_persisted(tmp_path):
    def failing_triage(leads, positioning, llm, model, persona=None):
        for lead in leads:
            lead.status = "unscored"           # scoring failed
        return leads

    store = LeadStore(tmp_path / "db.sqlite")
    run_pipeline(adapters=[OkAdapter()], store=store, positioning="POS", llm=None,
                 triage_model="t", draft_model="d", top_n=5, min_score=55,
                 telegram=("TOK", "42"), dry_run=False, enrich=False,
                 _triage=failing_triage, _draft=fake_draft,
                 _push=lambda leads, token, chat_id: list(leads))
    assert store.all() == []                            # unscored leads are not persisted
    fresh2, _ = ingest([OkAdapter()], store)
    assert len(fresh2) == 1                             # retried next run, never dropped silently


def test_run_pipeline_push_failure_not_marked(tmp_path):
    store = LeadStore(tmp_path / "db.sqlite")
    run_pipeline(adapters=[OkAdapter()], store=store, positioning="POS", llm=None,
                 triage_model="t", draft_model="d", top_n=5, min_score=55,
                 telegram=("TOK", "42"), dry_run=False, enrich=False,
                 _triage=_scoring_triage(90), _draft=fake_draft,
                 _push=lambda leads, token, chat_id: [])   # push fails entirely
    leads = store.all()
    assert len(leads) == 1 and leads[0].status == "scored"   # never mistakenly marked pushed


def test_run_pipeline_backlog_pushed_on_later_run(tmp_path):
    """A lead that clears min_score but misses the top_n cutoff is not lost: it stays
    in the scored backlog and is pushed on the next run."""
    scores = {"job 1": 90, "job 2": 91, "job 3": 92}

    class ThreeAdapter:
        name = "three"

        def fetch(self):
            return [RawItem(source="rss", external_id=str(i), url=f"http://x/{i}",
                            title=title, raw_text="b")
                    for i, title in enumerate(scores)]

    def fake_triage(leads, positioning, llm, model, persona=None):
        for lead in leads:
            lead.score = scores[lead.title]
            lead.status = "scored"
            lead.channel_action = "comment"
        return leads

    pushed = []

    def fake_push(leads, token, chat_id):
        pushed.extend(leads)
        return list(leads)

    store = LeadStore(tmp_path / "db.sqlite")
    kwargs = dict(adapters=[ThreeAdapter()], store=store, positioning="POS", llm=None,
                  triage_model="t", draft_model="d", top_n=1, min_score=55,
                  telegram=("TOK", "42"), dry_run=False, enrich=False,
                  _triage=fake_triage, _draft=fake_draft, _push=fake_push)
    run_pipeline(**kwargs)
    assert [lead.score for lead in pushed] == [92]       # first run: only the best lead
    run_pipeline(**kwargs)                               # second run: no new leads arrive
    assert [lead.score for lead in pushed] == [92, 91]   # backlog lead 91 is not lost


def test_run_pipeline_below_min_not_pushed(tmp_path):
    pushed = []

    def fake_push(leads, token, chat_id):
        pushed.extend(leads)
        return list(leads)

    store = LeadStore(tmp_path / "db.sqlite")
    r = run_pipeline(adapters=[OkAdapter()], store=store, positioning="POS", llm=None,
                     triage_model="t", draft_model="d", top_n=5, min_score=55,
                     telegram=("TOK", "42"), dry_run=False, enrich=False,
                     _triage=_scoring_triage(10), _draft=fake_draft, _push=fake_push)
    assert pushed == [] and r["drafted"] == 0          # below threshold: no draft, no push
