import logging
import time
from datetime import datetime, timezone
import feedparser
import httpx
from gig_radar.adapters.base import SourceAdapter
from gig_radar.models import RawItem

log = logging.getLogger("gig_radar")

DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


class RssAdapter(SourceAdapter):
    name = "rss"

    def __init__(self, feeds, agent=None, keywords=None, timeout=20, request_delay=2.0):
        self.feeds = feeds
        self.agent = agent or DEFAULT_UA
        self.keywords = [k.lower() for k in keywords] if keywords else None
        self.timeout = timeout
        self.request_delay = request_delay

    def _matches(self, text: str) -> bool:
        if not self.keywords:
            return True
        t = text.lower()
        return any(k in t for k in self.keywords)

    def _load(self, feed: str):
        # http(s) sources are fetched with httpx using a browser UA (works around Reddit and
        # others blocking feedparser's default UA), then parsed;
        # file:// and other local sources go straight to feedparser (used by test fixtures).
        if feed.startswith(("http://", "https://")):
            resp = httpx.get(feed, headers={"User-Agent": self.agent},
                             timeout=self.timeout, follow_redirects=True)
            resp.raise_for_status()
            return feedparser.parse(resp.text)
        return feedparser.parse(feed)

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        for idx, feed in enumerate(self.feeds):
            if idx > 0 and self.request_delay and feed.startswith(("http://", "https://")):
                time.sleep(self.request_delay)            # polite delay, avoids 429s from Reddit and others
            try:
                parsed = self._load(feed)
            except Exception as e:                        # noqa: BLE001 isolate per-feed failures
                log.warning("RSS feed failed: %s (%r)", feed, e)
                continue
            if getattr(parsed, "bozo", 0) and not parsed.entries:
                log.warning("RSS feed possibly failed: %s (%r)", feed,
                            getattr(parsed, "bozo_exception", None))
            for e in parsed.entries:
                link = e.get("link", "") if hasattr(e, "get") else ""
                if not link:
                    continue                              # no link means we can't dedup reliably, skip
                title = e.get("title", "")
                body = e.get("description", "") or e.get("summary", "")
                if not self._matches(f"{title}\n{body}"):
                    continue                              # keyword filter (only applied if configured)
                posted = None
                if getattr(e, "published_parsed", None):
                    posted = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
                items.append(RawItem(
                    source="rss",
                    external_id=str(link),
                    url=link,
                    title=title,
                    raw_text=body,
                    posted_at=posted,
                ))
        return items
