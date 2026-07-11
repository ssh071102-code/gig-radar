import logging
from typing import NamedTuple

import httpx

log = logging.getLogger("gig_radar")


class TelegramTarget(NamedTuple):
    """Delivery target for the digest. A NamedTuple, so a plain
    (token, chat_id) tuple works anywhere a TelegramTarget does."""

    token: str
    chat_id: str


def format_lead(lead) -> str:
    action = (lead.channel_action or "?").replace("_", " ")
    parts = [
        f"Score: {lead.score} | Category: {lead.category or '?'} | Suggested channel: {action}",
        f"Title: {lead.title}",
        f"Link: {lead.url}",
        "",
        f"Why: {lead.score_reason or ''}",
        "",
        "Draft (English, ready to send)",
        f"Opening: {lead.opening or ''}",
        "",
        lead.draft or "(none)",
    ]
    return "\n".join(parts)


def push_digest(leads, token: str, chat_id: str) -> list:
    """Step 5: send one Telegram message per lead. Returns the leads that were pushed
    successfully. A single failure never takes down the rest, is never mistakenly
    marked as pushed, and the token-bearing URL is never logged."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    pushed = []
    with httpx.Client(timeout=20) as client:
        for lead in leads:
            try:
                resp = client.post(url, json={
                    "chat_id": chat_id,
                    "text": format_lead(lead)[:4000],   # Telegram's 4096-char limit
                    "disable_web_page_preview": True,
                })
                resp.raise_for_status()
                pushed.append(lead)
            except Exception as e:                       # noqa: BLE001
                status = getattr(getattr(e, "response", None), "status_code", type(e).__name__)
                log.warning("telegram push failed for %s: %s", lead.id, status)
    return pushed
