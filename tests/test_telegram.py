import json
import logging

import httpx
import respx

from gig_radar.models import Lead
from gig_radar.push.telegram import push_digest, format_lead


def _lead(i="reddit:1", draft="Hi I built X"):
    return Lead(id=i, source="reddit", url="http://x", title="AI bot",
                raw_text="b", score=82, score_reason="good fit",
                channel_action="comment", draft=draft, opening="hook")


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


@respx.mock
def test_push_digest_isolates_failed_send_and_never_logs_token(caplog):
    respx.post("https://api.telegram.org/botSECRET-TOKEN/sendMessage").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"ok": True})])
    with caplog.at_level(logging.WARNING, logger="gig_radar"):
        pushed = push_digest([_lead("reddit:1"), _lead("reddit:2")],
                             token="SECRET-TOKEN", chat_id="42")
    assert [lead.id for lead in pushed] == ["reddit:2"]  # only the successful send
    warnings = [r.getMessage() for r in caplog.records if "push failed" in r.getMessage()]
    assert len(warnings) == 1 and "reddit:1" in warnings[0]
    assert all("SECRET-TOKEN" not in r.getMessage() for r in caplog.records)


@respx.mock
def test_push_digest_truncates_oversized_message():
    route = respx.post("https://api.telegram.org/botTOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True}))
    pushed = push_digest([_lead(draft="x" * 5000)], token="TOKEN", chat_id="42")
    assert len(pushed) == 1
    sent = json.loads(route.calls[0].request.content)["text"]
    assert len(sent) <= 4096                             # Telegram's hard message limit
