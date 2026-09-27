import sys
from types import SimpleNamespace

import pytest

from gig_radar.adapters.reddit import RedditAdapter


def _submission(id, title, body, created=1_700_000_000.0, author="poster"):
    return SimpleNamespace(
        id=id, title=title, selftext=body, created_utc=created,
        permalink=f"/r/forhire/{id}", author=SimpleNamespace(name=author),
    )


class FakeSub:
    def __init__(self, subs): self._subs = subs
    def new(self, limit=50): return self._subs


class FakeReddit:
    def __init__(self, mapping): self._mapping = mapping
    def subreddit(self, name): return FakeSub(self._mapping.get(name, []))


def test_reddit_keyword_filter():
    reddit = FakeReddit({"forhire": [
        _submission("a1", "[Hiring] AI automation engineer", "build LLM pipeline"),
        _submission("a2", "[Hiring] Dog walker", "walk my dog"),
    ]})
    ad = RedditAdapter(reddit=reddit, subreddits=["forhire"],
                       keywords=["AI", "LLM", "automation"], limit_per_sub=50)
    items = ad.fetch()
    ids = [i.external_id for i in items]
    assert ids == ["a1"]                    # only the keyword hit survives
    assert items[0].url.endswith("/r/forhire/a1")
    assert items[0].source == "reddit"


def test_reddit_without_praw_gives_install_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "praw", None)     # simulate praw not installed
    with pytest.raises(RuntimeError, match=r"gig-radar\[reddit\]"):
        RedditAdapter(subreddits=["forhire"], keywords=["AI"])
