import pytest
from pydantic import ValidationError

from gig_radar.models import Lead, RawItem


def test_lead_defaults():
    lead = Lead(id="reddit:abc", source="reddit", url="http://x", title="t", raw_text="body")
    assert lead.status == "new"
    assert lead.owner == "default"
    assert lead.score is None


def test_rawitem_minimal():
    raw = RawItem(source="rss", external_id="123", url="http://x", title="t", raw_text="b")
    assert raw.source == "rss"


from gig_radar.normalize import lead_id, raw_to_lead


def test_lead_id_stable():
    a = lead_id("reddit", "abc")
    b = lead_id("reddit", "abc")
    assert a == b and a.startswith("reddit:")


def test_lead_id_differs_by_source():
    assert lead_id("reddit", "abc") != lead_id("rss", "abc")


def test_raw_to_lead_sets_fetched_at():
    raw = RawItem(source="rss", external_id="g1", url="http://x", title="t", raw_text="b")
    lead = raw_to_lead(raw)
    assert lead.id == lead_id("rss", "g1")
    assert lead.fetched_at is not None
    assert lead.status == "new"


def test_validate_assignment_rejects_bad_status():
    lead = Lead(id="reddit:1", source="reddit", url="http://x", title="t", raw_text="b")
    with pytest.raises(ValidationError):
        lead.status = "bogus_status"
