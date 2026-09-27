from datetime import UTC, datetime

from gig_radar.adapters.base import SourceAdapter
from gig_radar.models import RawItem


def _make_client(client_id, client_secret, user_agent):
    """Build an authenticated praw client. praw is an optional extra, so a missing
    install fails here with an actionable message rather than at import time."""
    try:
        import praw
    except ImportError as e:
        raise RuntimeError(
            "the reddit source needs praw: pip install 'gig-radar[reddit]' "
            "(or disable `reddit:` in sources.yaml and use the logged-out .rss feeds)"
        ) from e
    return praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)


class RedditAdapter(SourceAdapter):
    name = "reddit"

    def __init__(self, subreddits, keywords, limit_per_sub=50, reddit=None,
                 client_id=None, client_secret=None, user_agent=None):
        self.subreddits = subreddits
        self.keywords = [k.lower() for k in keywords]
        self.limit_per_sub = limit_per_sub
        self.reddit = reddit or _make_client(client_id, client_secret, user_agent)

    def _matches(self, text: str) -> bool:
        t = text.lower()
        return any(k in t for k in self.keywords)

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        for name in self.subreddits:
            for s in self.reddit.subreddit(name).new(limit=self.limit_per_sub):
                blob = f"{s.title}\n{s.selftext}"
                if not self._matches(blob):
                    continue
                author = getattr(s.author, "name", None) if s.author else None
                items.append(RawItem(
                    source="reddit",
                    external_id=s.id,
                    url=f"https://www.reddit.com{s.permalink}",
                    title=s.title,
                    raw_text=s.selftext or "",
                    posted_at=datetime.fromtimestamp(s.created_utc, tz=UTC),
                    client_handle=author,
                ))
        return items
