import respx
import httpx
from gig_radar.brain.draft import enrich_context, draft_lead
from gig_radar.models import Lead


@respx.mock
def test_enrich_fetches_url_bounded():
    respx.get("https://co/about").mock(return_value=httpx.Response(200, text="<p>We build fintech</p>"))
    txt = enrich_context("https://co/about", max_chars=100)
    assert "fintech" in txt
    assert len(txt) <= 100


@respx.mock
def test_enrich_failure_returns_empty():
    respx.get("https://co/down").mock(return_value=httpx.Response(500))
    assert enrich_context("https://co/down") == ""


def _lead(action="comment"):
    return Lead(id="reddit:1", source="reddit", url="http://x", title="AI bot",
                raw_text="need an LLM bot", channel_action=action, score=80)


class FakeLLM:
    def __init__(self, ret):
        self.ret = ret
        self.seen = None

    def complete(self, model, system, user, max_tokens=2000):
        self.seen = user
        return self.ret


def test_draft_writes_draft_and_opening():
    llm = FakeLLM("OPENING: Saw your AI bot post\n===DRAFT===\nHi, I built X...")
    lead = draft_lead(_lead("comment"), positioning="POS", llm=llm, model="m", enrich=False)
    assert lead.draft.startswith("Hi, I built X")
    assert lead.opening == "Saw your AI bot post"


def test_draft_failure_degrades_without_raising():
    class BoomLLM:
        def complete(self, *a, **kw):
            raise RuntimeError("api down")

    lead = draft_lead(_lead("comment"), positioning="POS", llm=BoomLLM(), model="m", enrich=False)
    assert lead.draft == ""
    assert lead.opening == "(draft failed, write manually)"


def test_draft_passes_channel_action_to_prompt():
    llm = FakeLLM("OPENING: o\n===DRAFT===\nd")
    draft_lead(_lead("email"), positioning="POS", llm=llm, model="m", enrich=False)
    assert "email" in llm.seen
