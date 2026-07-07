from gig_radar.config import load_config
from gig_radar.models import RawItem
from gig_radar.store import LeadStore
from gig_radar.pipeline import ingest, run_pipeline


def test_load_config(tmp_path):
    (tmp_path / "settings.yaml").write_text("top_n: 5\nmin_score_to_push: 60\n", encoding="utf-8")
    (tmp_path / "sources.yaml").write_text("reddit:\n  enabled: false\n", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.settings["top_n"] == 5
    assert cfg.sources["reddit"]["enabled"] is False


class OkAdapter:
    name = "ok"
    def fetch(self):
        return [RawItem(source="rss", external_id="1", url="http://x", title="AI job", raw_text="b")]


class BoomAdapter:
    name = "boom"
    def fetch(self):
        raise RuntimeError("source down")


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
    for l in first:
        store.upsert(l)                          # simulate run_pipeline persisting after success
    second, _ = ingest([OkAdapter()], store)     # same source runs again
    assert len(second) == 0                       # already persisted, deduped


def test_run_pipeline_dry_run_pushes_nothing(tmp_path):
    calls = {"push": 0}
    def fake_triage(leads, positioning, llm, model):
        for l in leads: l.score = 90; l.status = "scored"; l.channel_action = "comment"
        return leads
    def fake_draft(lead, positioning, llm, model, enrich): lead.draft = "d"; return lead
    def fake_push(leads, token, chat_id): calls["push"] += len(leads); return list(leads)

    store = LeadStore(tmp_path / "db.sqlite")
    result = run_pipeline(
        adapters=[OkAdapter()], store=store, positioning="POS", llm=None,
        triage_model="t", draft_model="d", top_n=5, min_score=55,
        telegram=("TOK", "42"), dry_run=True, enrich=False,
        _triage=fake_triage, _draft=fake_draft, _push=fake_push,
    )
    assert calls["push"] == 0                 # dry-run never pushes
    assert result["scored"] == 1 and result["drafted"] == 1
    assert store.all() == []              # dry-run has no persistence side effects


def test_run_pipeline_real_push_marks_pushed(tmp_path):
    def fake_triage(leads, positioning, llm, model):
        for l in leads: l.score = 90; l.status = "scored"; l.channel_action = "comment"
        return leads
    def fake_draft(lead, positioning, llm, model, enrich): lead.draft = "d"; return lead
    pushed = []
    def fake_push(leads, token, chat_id): pushed.extend(leads); return list(leads)

    store = LeadStore(tmp_path / "db.sqlite")
    run_pipeline(adapters=[OkAdapter()], store=store, positioning="POS", llm=None,
                 triage_model="t", draft_model="d", top_n=5, min_score=55,
                 telegram=("TOK", "42"), dry_run=False, enrich=False,
                 _triage=fake_triage, _draft=fake_draft, _push=fake_push)
    assert len(pushed) == 1
    assert store.get(pushed[0].id).status == "pushed"    # status written back


def test_run_pipeline_unscored_not_persisted(tmp_path):
    def fake_triage(leads, positioning, llm, model):
        for l in leads: l.status = "unscored"          # scoring failed
        return leads
    def fake_draft(lead, positioning, llm, model, enrich): return lead
    def fake_push(leads, token, chat_id): return list(leads)
    store = LeadStore(tmp_path / "db.sqlite")
    run_pipeline(adapters=[OkAdapter()], store=store, positioning="POS", llm=None,
                 triage_model="t", draft_model="d", top_n=5, min_score=55,
                 telegram=("TOK", "42"), dry_run=False, enrich=False,
                 _triage=fake_triage, _draft=fake_draft, _push=fake_push)
    assert store.all() == []                            # unscored leads are not persisted
    fresh2, _ = ingest([OkAdapter()], store)
    assert len(fresh2) == 1                             # retried next run, never dropped silently

def test_run_pipeline_push_failure_not_marked(tmp_path):
    def fake_triage(leads, positioning, llm, model):
        for l in leads: l.score = 90; l.status = "scored"; l.channel_action = "comment"
        return leads
    def fake_draft(lead, positioning, llm, model, enrich): lead.draft = "d"; return lead
    def fake_push(leads, token, chat_id): return []    # push fails entirely
    store = LeadStore(tmp_path / "db.sqlite")
    run_pipeline(adapters=[OkAdapter()], store=store, positioning="POS", llm=None,
                 triage_model="t", draft_model="d", top_n=5, min_score=55,
                 telegram=("TOK", "42"), dry_run=False, enrich=False,
                 _triage=fake_triage, _draft=fake_draft, _push=fake_push)
    leads = store.all()
    assert len(leads) == 1 and leads[0].status == "scored"   # never mistakenly marked pushed

def test_run_pipeline_below_min_not_pushed(tmp_path):
    def fake_triage(leads, positioning, llm, model):
        for l in leads: l.score = 10; l.status = "scored"; l.channel_action = "comment"
        return leads
    def fake_draft(lead, positioning, llm, model, enrich): lead.draft = "d"; return lead
    pushed = []
    def fake_push(leads, token, chat_id): pushed.extend(leads); return list(leads)
    store = LeadStore(tmp_path / "db.sqlite")
    r = run_pipeline(adapters=[OkAdapter()], store=store, positioning="POS", llm=None,
                     triage_model="t", draft_model="d", top_n=5, min_score=55,
                     telegram=("TOK", "42"), dry_run=False, enrich=False,
                     _triage=fake_triage, _draft=fake_draft, _push=fake_push)
    assert pushed == [] and r["drafted"] == 0          # below threshold: no draft, no push
