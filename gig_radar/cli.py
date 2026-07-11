import logging
from pathlib import Path
import typer
from gig_radar.config import load_config, env
from gig_radar.store import LeadStore
from gig_radar.llm import LLM
from gig_radar.pipeline import run_pipeline
from gig_radar.adapters.rss import RssAdapter
from gig_radar.adapters.reddit import RedditAdapter
from gig_radar.adapters.upwork import UpworkBoardAdapter

app = typer.Typer(help="gig-radar -- automated lead-gen + LLM proposal drafting")
ROOT = Path(__file__).resolve().parent.parent


def _build_adapters(sources: dict):
    adapters = []
    if sources.get("reddit", {}).get("enabled"):
        r = sources["reddit"]
        adapters.append(RedditAdapter(
            subreddits=r["subreddits"], keywords=r["keywords"],
            limit_per_sub=r.get("limit_per_sub", 50),
            client_id=env("REDDIT_CLIENT_ID"), client_secret=env("REDDIT_CLIENT_SECRET"),
            user_agent=env("REDDIT_USER_AGENT")))
    if sources.get("rss", {}).get("enabled"):
        rss = sources["rss"]
        adapters.append(RssAdapter(feeds=rss["feeds"], agent=rss.get("user_agent"),
                                   keywords=rss.get("keywords"),
                                   request_delay=rss.get("request_delay", 2.0)))
    if sources.get("upwork", {}).get("enabled"):
        adapters.append(UpworkBoardAdapter(saved_searches=sources["upwork"]["saved_searches"]))
    return adapters


def _require_env(*keys: str) -> None:
    """Fail fast with a clear message instead of an SDK stack trace mid-run
    (or, worse, a request to a literal 'None' Telegram URL)."""
    missing = [k for k in keys if not env(k)]
    if missing:
        raise typer.BadParameter(
            f"missing environment variable(s): {', '.join(missing)}. "
            "Set them in secrets/.env (see secrets/.env.example) or export them."
        )


def _run(dry_run: bool):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(ROOT / "config", secrets_env=ROOT / "secrets" / ".env")
    _require_env("ANTHROPIC_API_KEY")
    if not dry_run:
        _require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    positioning = (ROOT / "config" / "positioning.md").read_text("utf-8")
    store = LeadStore(ROOT / "data" / "leads.sqlite")
    llm = LLM(api_key=env("ANTHROPIC_API_KEY"), base_url=env("ANTHROPIC_BASE_URL"))
    s = cfg.settings
    result = run_pipeline(
        adapters=_build_adapters(cfg.sources), store=store, positioning=positioning, llm=llm,
        triage_model=s["triage_model"], draft_model=s["draft_model"],
        top_n=s["top_n"], min_score=s["min_score_to_push"],
        telegram=(env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")),
        dry_run=dry_run, enrich=s.get("enrich", True), persona=s.get("persona"))
    typer.echo(result)


@app.command()
def run():
    """Run the full pipeline and push results to Telegram."""
    _run(dry_run=False)


@app.command(name="dry-run")
def dry_run():
    """Run the full pipeline without pushing (local dry run)."""
    _run(dry_run=True)


@app.command(name="init-positioning")
def init_positioning():
    """Generate a positioning.md template (review and edit before use)."""
    path = ROOT / "config" / "positioning.md"
    if path.exists():
        typer.echo(f"Already exists: {path}")
        raise typer.Exit()
    path.write_text(_POSITIONING_TEMPLATE, encoding="utf-8")
    typer.echo(f"Template generated: {path} -- review and edit before use")


_POSITIONING_TEMPLATE = """# Positioning & Case Studies

## One-line positioning
I help <ideal client> achieve <outcome> using AI integration, automation, and AI video.

## Case cards
### Case 1: <case study title>
- What was built:
- Result:
- Transferable to:

### Case 2: <case study title>
- What was built:
- Result:
- Transferable to:

### Case 3: <case study title>
- What was built:
- Result:
- Transferable to:

## Rate anchor
- $/hr or fixed-price range:

## Tone
-
"""


if __name__ == "__main__":
    app()
