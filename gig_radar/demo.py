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

DEMO_POSITIONING = """# Positioning & Case Studies (demo fixture)

## One-line positioning
I help small SaaS teams ship AI features -- RAG chatbots, LLM automations, AI video.

## Case cards
### Case 1: Support chatbot over product docs
- What was built: RAG pipeline + chat widget grounded in the company's docs
- Result: first-response time cut from hours to seconds
- Transferable to: any docs-heavy product

## Rate anchor
- Fixed-price per scoped deliverable

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
            url="https://example.com/jobs/toptal-ml",
            title="[Hiring] Senior ML engineer, Toptal-vetted only",
            raw_text="Looking for a Toptal-vetted senior ML engineer with an "
                     "established platform rating and enterprise references."),
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
    "Toptal-vetted": (28, "other", "comment",
                      "Requires an established platform rating a newcomer lacks"),
    "WordPress theme": (12, "other", "comment",
                        "Out of wheelhouse; plain theme CSS work"),
}

# title-key -> canned draft (only leads that clear the top-N gate get drafted)
_DRAFTS = {
    "support chatbot": (
        "OPENING: Grounded-in-your-docs chatbot with citations -- shipped this exact thing.\n"
        "===DRAFT===\n"
        "I built a RAG support chatbot for a docs-heavy SaaS: retrieval over the docs, "
        "answers with citations, and a fallback to a human when confidence is low. "
        "First-response time went from hours to seconds.\n\n"
        "For your ~2k tickets/month I'd start with a one-week scoped build: index your docs, "
        "stand up the chat endpoint, and measure deflection on real tickets before you "
        "commit further. Happy to share the eval setup I use to keep answers honest."),
    "weekly ops reporting": (
        "OPENING: That day-per-week of copy-paste is exactly what I automate.\n"
        "===DRAFT===\n"
        "Subject: Airtable-to-Slack reporting on autopilot\n\n"
        "You describe a day per week lost to moving numbers between Airtable, Sheets and "
        "Slack. I build exactly these bridges: a scheduled job pulls from Airtable, "
        "computes the weekly rollups, and posts a formatted digest to Slack -- no human "
        "in the loop, with an audit log so you can trust the numbers."),
    "product demo video": (
        "OPENING: AI-made demo video that does not look AI-made.\n"
        "===DRAFT===\n"
        "For a 60-90s launch demo I storyboard from your actual product flow, generate "
        "scenes with current AI video tooling, and cut it to a voiceover script that "
        "sells the outcome, not the features. You review at storyboard and rough-cut "
        "stages, so nothing ships that you have not signed off."),
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
    echo("Scored leads (demo fixtures):")
    for lead in scored:
        echo(f"  {lead.score:>3}  {lead.category or 'other':<15} {lead.title}")
    echo("")
    top = sent[0]
    echo(f"Drafted proposal for the top lead ({top.score}, {top.channel_action}):")
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
