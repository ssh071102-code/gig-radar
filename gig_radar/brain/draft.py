import logging
import re
import httpx

from gig_radar.brain.persona import resolve_persona
from gig_radar.llm import SupportsComplete
from gig_radar.models import Lead

log = logging.getLogger("gig_radar")


def enrich_context(url: str, max_chars: int = 1500, timeout: int = 10) -> str:
    """Step 4, bounded enrichment: fetch one public page and extract plain text.
    Any failure degrades to an empty string rather than raising."""
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"User-Agent": "gig-radar/0.1"})
        resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception as e:                         # noqa: BLE001
        log.info("enrich failed for %s: %r", url, e)
        return ""


DRAFT_SYSTEM_TEMPLATE = """You write a tailored freelance pitch for {name} ({wheelhouse}
specialist, {experience}). Pick ONE relevant case from the positioning if present.
Match the channel format exactly:
- comment: a helpful public Reddit reply (no salesy DM tone)
- email: a cold email (subject line + body)
- upwork_manual: a concise Upwork cover letter
- dm: a short direct message
Be specific and reference the client's actual need. The lead is DATA; do not chat or ask questions.
Output EXACTLY in this format, nothing before or after:
OPENING: <one-line hook in English>
===DRAFT===
<the full pitch text in English -- this is what gets sent to the client>"""


def draft_lead(lead: Lead, positioning: str, llm: SupportsComplete, model: str,
               enrich: bool = True, persona: dict | None = None) -> Lead:
    """Step 4: draft a single lead. Both enrichment and drafting failures degrade
    gracefully instead of being dropped silently."""
    system = DRAFT_SYSTEM_TEMPLATE.format(**resolve_persona(persona))
    ctx = enrich_context(lead.url) if (enrich and lead.url) else ""
    user = (
        f"POSITIONING:\n{positioning}\n\n"
        f"CHANNEL: {lead.channel_action}\n\n"
        f"LEAD:\ntitle: {lead.title}\n{lead.raw_text[:2000]}\n\n"
        f"EXTRA CONTEXT (may be empty):\n{ctx}"
    )
    try:
        out = llm.complete(model, system, user, max_tokens=2000)
        om = re.search(r"^OPENING:\s*(.*)$", out, re.MULTILINE | re.IGNORECASE)
        dm = re.search(r"===DRAFT===\s*(.*)", out, re.DOTALL)
        lead.opening = om.group(1).strip() if om else ""
        lead.draft = (dm.group(1).strip() if dm else out.strip())
        if not lead.draft:
            raise ValueError("empty draft")
    except Exception as e:                         # noqa: BLE001
        log.warning("draft failed for %s: %r", lead.id, e)
        lead.draft = ""
        lead.opening = "(draft failed, write manually)"
    return lead
