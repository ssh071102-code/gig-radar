from typer.testing import CliRunner

from gig_radar import cli
from gig_radar.demo import run_demo

_ENV_KEYS = ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "TELEGRAM_BOT_TOKEN",
             "TELEGRAM_CHAT_ID", "GIG_RADAR_HOME")


def test_demo_runs_with_no_env_vars(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    result = CliRunner().invoke(cli.app, ["demo"])
    assert result.exit_code == 0
    assert "no network, no API keys" in result.output
    assert "Telegram message" in result.output
    assert "would be pushed" in result.output


def test_demo_is_deterministic():
    first: list[str] = []
    second: list[str] = []
    r1 = run_demo(echo=first.append)
    r2 = run_demo(echo=second.append)
    assert first == second
    assert r1 == r2
    assert r1["pushed"] == 3 and r1["fresh"] == 5
