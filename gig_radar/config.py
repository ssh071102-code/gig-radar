import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class Config:
    settings: dict
    sources: dict


def load_config(config_dir, secrets_env: Path | None = None) -> Config:
    config_dir = Path(config_dir)
    if secrets_env and Path(secrets_env).exists():
        load_dotenv(secrets_env)
    settings = yaml.safe_load((config_dir / "settings.yaml").read_text("utf-8")) or {}
    sources = yaml.safe_load((config_dir / "sources.yaml").read_text("utf-8")) or {}
    return Config(settings=settings, sources=sources)


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)
