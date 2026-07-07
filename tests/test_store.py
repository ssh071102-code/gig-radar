from gig_radar.models import Lead
from gig_radar.store import LeadStore


def _lead(i="reddit:1", status="new"):
    return Lead(id=i, source="reddit", url="http://x", title="t", raw_text="b", status=status)


def test_upsert_and_exists(tmp_path):
    s = LeadStore(tmp_path / "db.sqlite")
    assert not s.exists("reddit:1")
    s.upsert(_lead())
    assert s.exists("reddit:1")

def test_upsert_idempotent(tmp_path):
    s = LeadStore(tmp_path / "db.sqlite")
    s.upsert(_lead())
    s.upsert(_lead())                      # store the same id again
    assert len(s.all()) == 1               # no duplicate

def test_new_leads_filters_seen(tmp_path):
    s = LeadStore(tmp_path / "db.sqlite")
    s.upsert(_lead("reddit:1"))
    incoming = [_lead("reddit:1"), _lead("reddit:2")]
    fresh = s.filter_unseen(incoming)
    assert [l.id for l in fresh] == ["reddit:2"]

def test_mark_status(tmp_path):
    s = LeadStore(tmp_path / "db.sqlite")
    s.upsert(_lead())
    s.mark("reddit:1", "pushed")
    assert s.get("reddit:1").status == "pushed"

def test_filter_unseen_dedups_within_batch(tmp_path):
    s = LeadStore(tmp_path / "db.sqlite")
    incoming = [_lead("reddit:9"), _lead("reddit:9"), _lead("reddit:8")]
    fresh = s.filter_unseen(incoming)
    assert [l.id for l in fresh] == ["reddit:9", "reddit:8"]   # duplicates within a batch collapse to one

def test_all_skips_corrupt_row(tmp_path):
    s = LeadStore(tmp_path / "db.sqlite")
    s.upsert(_lead("reddit:1"))
    s.conn.execute("INSERT INTO leads(id,status,data) VALUES('bad','new','{not json}')")
    s.conn.commit()
    leads = s.all()                                            # should not raise
    assert [l.id for l in leads] == ["reddit:1"]               # the corrupt row is skipped

def test_validate_assignment_rejects_bad_status(tmp_path):
    import pytest
    from pydantic import ValidationError
    l = _lead()
    with pytest.raises(ValidationError):
        l.status = "bogus_status"
