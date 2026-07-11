import logging
import os
from pathlib import Path
from typing import Optional

import typer

from gig_radar.adapters.base import SourceAdapter
from gig_radar.config import load_config, env
from gig_radar.store import LeadStore
from gig_radar.llm import LLM
from gig_radar.pipeline import run_pipeline
from gig_radar.push.telegram import TelegramTarget
from gig_radar.templates import POSITIONING_TEMPLATE
from gig_radar.adapters.rss import RssAdapter
from gig_radar.adapters.reddit import RedditAdapter
from gig_radar.adapters.upwork import UpworkBoardAdapter

app = typer.Typer(help="gig-radar -- automated lead-gen + LLM proposal drafting")

_CONFIG_DIR_OPT = typer.Option(
    None, "--config-dir",
    help="Directory holding settings.yaml / sources.yaml / positioning.md "
         "(default: <root>/config).")


def _root() -> Path:
    """Working root for config/, secrets/ and data/. Defaults to the current
    directory; set GIG_RADAR_HOME to pin it. Never resolves relative to the
    package itself, so a non-editable install never reads or writes site-packages."""
    home = os.environ.get("GIG_RADAR_HOME")
    return Path(home).expanduser() if home else Path.cwd()


def _build_adapters(sources: dict) -> list[SourceAdapter]:
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


def _run(dry_run: bool, config_dir: Optional[Path] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    root = _root()
    config_dir = Path(config_dir) if config_dir else root / "config"
    cfg = load_config(config_dir, secrets_env=root / "secrets" / ".env")
    _require_env("ANTHROPIC_API_KEY")
    if not dry_run:
        _require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    positioning_path = config_dir / "positioning.md"
    if not positioning_path.exists():
        raise typer.BadParameter(
            f"no positioning file at {positioning_path}. "
            "Run `gig-radar init-positioning` to generate one, then edit it -- "
            "scoring and drafting are anchored to it."
        )
    positioning = positioning_path.read_text("utf-8")
    store = LeadStore(root / "data" / "leads.sqlite")
    llm = LLM(api_key=env("ANTHROPIC_API_KEY"), base_url=env("ANTHROPIC_BASE_URL"))
    s = cfg.settings
    result = run_pipeline(
        adapters=_build_adapters(cfg.sources), store=store, positioning=positioning, llm=llm,
        triage_model=s["triage_model"], draft_model=s["draft_model"],
        top_n=s["top_n"], min_score=s["min_score_to_push"],
        telegram=TelegramTarget(env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")),
        dry_run=dry_run, enrich=s.get("enrich", True), persona=s.get("persona"))
    typer.echo(result)


@app.command()
def demo():
    """Run the full pipeline on bundled fixture leads -- no network, no API keys."""
    from gig_radar.demo import run_demo
    run_demo(echo=typer.echo)


@app.command()
def run(config_dir: Optional[Path] = _CONFIG_DIR_OPT):
    """Run the full pipeline and push results to Telegram."""
    _run(dry_run=False, config_dir=config_dir)


@app.command(name="dry-run")
def dry_run(config_dir: Optional[Path] = _CONFIG_DIR_OPT):
    """Run the full pipeline without pushing (local dry run)."""
    _run(dry_run=True, config_dir=config_dir)


@app.command(name="init-positioning")
def init_positioning(config_dir: Optional[Path] = _CONFIG_DIR_OPT):
    """Generate a positioning.md template (review and edit before use)."""
    config_dir = Path(config_dir) if config_dir else _root() / "config"
    path = config_dir / "positioning.md"
    if path.exists():
        typer.echo(f"Already exists: {path}")
        raise typer.Exit()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(POSITIONING_TEMPLATE, encoding="utf-8")
    typer.echo(f"Template generated: {path} -- review and edit before use")


if __name__ == "__main__":
    app()
