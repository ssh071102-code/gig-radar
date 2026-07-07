import respx, httpx
from gig_radar.models import Lead
from gig_radar.push.telegram import push_digest, format_lead


def _lead():
    return Lead(id="reddit:1", source="reddit", url="http://x", title="AI bot",
                raw_text="b", score=82, score_reason="good fit",
                channel_action="comment", draft="Hi I built X", opening="hook")


def test_format_lead_contains_key_fields():
    msg = format_lead(_lead())
    assert "82" in msg and "AI bot" in msg and "Hi I built X" in msg and "http://x" in msg
    assert "Score:" in msg and "Category:" in msg and "Opening:" in msg


@respx.mock
def test_push_digest_posts_each_lead():
    route = respx.post("https://api.telegram.org/botTOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True}))
    pushed = push_digest([_lead(), _lead()], token="TOKEN", chat_id="42")
    assert len(pushed) == 2
    assert route.call_count == 2
