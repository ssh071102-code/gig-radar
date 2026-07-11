import pytest
import typer
from typer.testing import CliRunner

from gig_radar import cli


def test_root_defaults_to_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("GIG_RADAR_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    assert cli._root() == tmp_path


def test_root_honors_gig_radar_home(monkeypatch, tmp_path):
    monkeypatch.setenv("GIG_RADAR_HOME", str(tmp_path))
    assert cli._root() == tmp_path


def test_require_env_raises_helpful_message(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(typer.BadParameter, match="ANTHROPIC_API_KEY"):
        cli._require_env("ANTHROPIC_API_KEY")


def test_require_env_passes_when_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    cli._require_env("ANTHROPIC_API_KEY")               # does not raise


def test_init_positioning_writes_template_to_config_dir(tmp_path):
    result = CliRunner().invoke(cli.app, ["init-positioning", "--config-dir", str(tmp_path)])
    assert result.exit_code == 0
    body = (tmp_path / "positioning.md").read_text("utf-8")
    assert "One-line positioning" in body


def test_init_positioning_never_overwrites(tmp_path):
    (tmp_path / "positioning.md").write_text("mine", encoding="utf-8")
    result = CliRunner().invoke(cli.app, ["init-positioning", "--config-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "positioning.md").read_text("utf-8") == "mine"
    assert "Already exists" in result.output


def test_committed_example_matches_template():
    """config/positioning.example.md is a rendered copy of the single template source;
    this guards against the two drifting apart."""
    from pathlib import Path

    from gig_radar.templates import POSITIONING_TEMPLATE
    example = Path(__file__).parent.parent / "config" / "positioning.example.md"
    assert example.read_text("utf-8") == POSITIONING_TEMPLATE


def test_run_without_positioning_points_at_init(monkeypatch, tmp_path):
    (tmp_path / "settings.yaml").write_text(
        "top_n: 1\nmin_score_to_push: 55\ntriage_model: t\ndraft_model: d\n", encoding="utf-8")
    (tmp_path / "sources.yaml").write_text("rss:\n  enabled: false\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    result = CliRunner().invoke(cli.app, ["dry-run", "--config-dir", str(tmp_path)])
    assert result.exit_code != 0
    assert "init-positioning" in result.output
