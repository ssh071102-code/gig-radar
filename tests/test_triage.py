from gig_radar.models import Lead
from gig_radar.brain.triage import triage


def _lead(i):
    return Lead(id=i, source="reddit", url="http://x", title=f"job {i}", raw_text="build AI bot")


class FakeLLM:
    def __init__(self, mapping):
        self.mapping = mapping

    def complete(self, model, system, user, max_tokens=2000):
        for key, val in self.mapping.items():
            if key in user:
                if isinstance(val, Exception):
                    raise val
                return val
        raise AssertionError("no match")


def test_triage_scores_and_sorts():
    leads = [_lead("a"), _lead("b")]
    llm = FakeLLM({
        "job a": "SCORE: 40\nCATEGORY: automation\nCHANNEL: comment\nREASON: low budget",
        "job b": "SCORE: 85\nCATEGORY: ai-integration\nCHANNEL: comment\nREASON: great fit",
    })
    out = triage(leads, positioning="POS", llm=llm, model="m")
    assert [l.id for l in out] == ["b", "a"]
    assert out[0].score == 85 and out[0].status == "scored"


def test_triage_failure_marks_unscored():
    leads = [_lead("a")]
    llm = FakeLLM({"job a": RuntimeError("api down")})
    out = triage(leads, positioning="POS", llm=llm, model="m")
    assert out[0].status == "unscored"
    assert out[0].score is None


def test_triage_sanitizes_bad_enum():
    leads = [_lead("a")]
    llm = FakeLLM({"job a": "SCORE: 70\nCATEGORY: AI Integration\nCHANNEL: apply\nREASON: ok"})
    out = triage(leads, positioning="POS", llm=llm, model="m")
    assert out[0].status == "scored"
    assert out[0].category == "other"
    assert out[0].channel_action == "comment"


def test_triage_clamps_score():
    leads = [_lead("a")]
    llm = FakeLLM({"job a": "SCORE: 150\nCATEGORY: automation\nCHANNEL: comment\nREASON: x"})
    out = triage(leads, positioning="POS", llm=llm, model="m")
    assert out[0].score == 100
