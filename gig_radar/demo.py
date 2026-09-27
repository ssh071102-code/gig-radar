"""Zero-key demo: the full pipeline against bundled fixture leads.

Everything here is deterministic and offline -- a fixture adapter instead of live
sources, a canned LLM instead of the Anthropic client (same shape as the fake used
in the test suite), an in-memory store, and a push step that prints instead of
calling Telegram. `gig-radar demo` runs with no environment variables at all.
"""

from gig_radar.models import RawItem
from gig_radar.pipeline import run_pipeline
from gig_radar.push.telegram import TelegramTarget, format_lead
from gig_radar.store import LeadStore

# The demo profile is deliberately left as a template. Canned drafts below quote these
# placeholders instead of inventing a track record; a real run fills them from the
# user's own config/positioning.md.
DEMO_POSITIONING = """# Positioning & Case Studies (demo fixture)

## One-line positioning
<what you build, and for whom>

## Case cards
### Case 1: <your case title>
- What was built: <what you built>
- Result: <the result, in your own numbers>
- Transferable to: <where it applies>

## Tone
- Direct, specific, no fluff
"""

FIXTURE_ITEMS = [
    RawItem(source="rss", external_id="demo-1",
            url="https://example.com/jobs/rag-chatbot",
            title="[Hiring] Build a support chatbot grounded in our product docs (RAG)",
            raw_text="SaaS startup, ~2k support tickets/month. We want an LLM chatbot "
                     "that answers from our docs with citations. Budget $3-5k."),
    RawItem(source="rss", external_id="demo-2",
            url="https://example.com/jobs/report-automation",
            title="[Hiring] Automate weekly ops reporting from Airtable and Slack",
            raw_text="Ops team burns a day per week copying numbers between Airtable, "
                     "Sheets and Slack. Want it automated end to end."),
    RawItem(source="rss", external_id="demo-3",
            url="https://example.com/jobs/launch-video",
            title="[Hiring] AI-generated product demo video for our launch",
            raw_text="60-90s product demo video for a launch page. Open to AI video "
                     "tooling if the result looks professional."),
    RawItem(source="rss", external_id="demo-4",
            url="https://example.com/jobs/staff-ml",
            title="[Hiring] Staff ML engineer, 8+ years, full-time",
            raw_text="Full-time role. 8+ years of production ML, prior staff-level "
                     "scope and enterprise references required."),
    RawItem(source="rss", external_id="demo-5",
            url="https://example.com/jobs/wordpress-theme",
            title="[Hiring] Fix the fonts on my WordPress theme",
            raw_text="Small blog, the heading font renders wrong on mobile."),
]

# title-key -> (score, category, channel, reason)
_TRIAGE = {
    "support chatbot": (92, "ai-integration", "comment",
                        "Direct wheelhouse fit with a stated budget and clear scope"),
    "weekly ops reporting": (84, "automation", "email",
                             "Well-scoped automation with obvious weekly ROI"),
    "product demo video": (76, "ai-video", "dm",
                           "AI-video fit; client already open to AI tooling"),
    "Staff ML engineer": (28, "other", "email",
                          "Asks for 8+ years at staff level, well above the persona"),
    "WordPress theme": (12, "other", "comment",
                        "Out of wheelhouse; plain theme CSS work"),
}

# title-key -> canned draft (only leads that clear the top-N gate get drafted)
_DRAFTS = {
    "support chatbot": (
        "OPENING: Docs-grounded support chatbot with citations, scoped to your ticket volume.\n"
        "===DRAFT===\n"
        "Relevant work: <Case 1 from your positioning: what you built, and the result>.\n\n"
        "For ~2k tickets/month I would start with a one-week first milestone: index your "
        "docs, stand up a chat endpoint that answers with citations and hands off to a "
        "human when unsure, and measure deflection on a sample of real tickets before "
        "you commit further."),
    "weekly ops reporting": (
        "OPENING: Your weekly Airtable-to-Slack copy-paste can run on a schedule.\n"
        "===DRAFT===\n"
        "Subject: Automating the weekly ops report\n\n"
        "You describe a day per week spent moving numbers between Airtable, Sheets and "
        "Slack. Proposed approach: a scheduled job pulls from Airtable, computes the "
        "weekly rollups and posts a formatted digest to Slack, with a run log so the "
        "numbers can be checked.\n\n"
        "Relevant work: <a case from your positioning, if one fits>."),
    "product demo video": (
        "OPENING: A 60-90s launch demo built from your real product flow.\n"
        "===DRAFT===\n"
        "Proposed approach: storyboard from your actual product flow, generate scenes "
        "with AI video tooling, and cut to a short voiceover script. You review at the "
        "storyboard and rough-cut stages before anything is final.\n\n"
        "Relevant work: <a case from your positioning, if one fits>."),
}


class _DemoAdapter:
    name = "demo-fixtures"

    def fetch(self) -> list[RawItem]:
        return list(FIXTURE_ITEMS)


class DemoLLM:
    """Deterministic stand-in for the Anthropic client."""

    def complete(self, model: str, system: str, user: str, max_tokens: int = 1500) -> str:
        table = _TRIAGE if "SCORE:" in system else _DRAFTS
        for key, val in table.items():
            if key in user:
                if table is _TRIAGE:
                    score, cat, channel, reason = val
                    return (f"SCORE: {score}\nCATEGORY: {cat}\n"
                            f"CHANNEL: {channel}\nREASON: {reason}")
                return val
        return "SCORE: 0\nCATEGORY: other\nCHANNEL: comment\nREASON: no fixture match"


def run_demo(echo=print) -> dict:
    """Run the real pipeline wiring end to end on fixture data and print what a
    real run would deliver. Returns the pipeline result dict."""
    sent: list = []

    def capture_push(leads, token, chat_id):
        sent.extend(leads)
        return list(leads)

    with LeadStore(":memory:") as store:
        result = run_pipeline(
            adapters=[_DemoAdapter()], store=store, positioning=DEMO_POSITIONING,
            llm=DemoLLM(), triage_model="demo-triage", draft_model="demo-draft",
            top_n=3, min_score=55, telegram=TelegramTarget("demo-token", "demo-chat"),
            dry_run=False, enrich=False, _push=capture_push)
        scored = sorted(store.all(), key=lambda lead: lead.score or 0, reverse=True)

    echo("gig-radar demo -- bundled fixture data, no network, no API keys")
    echo("")
    echo("Scored postings (demo fixtures):")
    for lead in scored:
        echo(f"  {lead.score:>3}  {lead.category or 'other':<15} {lead.title}")
    echo("")
    top = sent[0]
    echo(f"Drafted reply for the top posting ({top.score}, {top.channel_action}):")
    echo(f"  {top.opening}")
    for line in (top.draft or "").splitlines():
        echo(f"  {line}")
    echo("")
    echo("Exact Telegram message that WOULD be sent for it:")
    echo("-" * 60)
    echo(format_lead(top)[:4000])            # same truncation as the real push step
    echo("-" * 60)
    echo(f"(demo run: {result['fresh']} ingested, {result['scored']} scored, "
         f"{result['drafted']} drafted, {result['pushed']} would be pushed)")
    return result
