import logging
import re
import httpx
from gig_radar.adapters.base import SourceAdapter
from gig_radar.models import RawItem

log = logging.getLogger("gig_radar")

_JOB_RE = re.compile(r'href="(/jobs/[^"]+~[0-9a-f]+)"[^>]*>(.*?)</a>', re.S)


class UpworkBoardAdapter(SourceAdapter):
    """Best-effort HTML scrape of public Upwork saved-search pages.

    Upwork sits behind Cloudflare, so unauthenticated fetches are frequently
    blocked (403 / challenge page yields zero matches). Treat this source as a
    manual review queue, not a reliable feed -- the RSS route is the production
    path. A blocked or failing search never takes down the others.
    """

    name = "upwork"

    def __init__(self, saved_searches: list[str], timeout=15):
        self.saved_searches = saved_searches
        self.timeout = timeout

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        headers = {"User-Agent": "Mozilla/5.0 gig-radar"}
        for url in self.saved_searches:
            try:
                resp = httpx.get(url, headers=headers, timeout=self.timeout,
                                 follow_redirects=True)
                resp.raise_for_status()
            except Exception as exc:                   # noqa: BLE001 isolate per-URL failures
                log.warning("Upwork search failed: %s (%r)", url, exc)
                continue
            for href, title in _JOB_RE.findall(resp.text):
                ext = href.rsplit("~", 1)[-1].strip('"/')
                clean = re.sub(r"<[^>]+>", "", title).strip()
                items.append(RawItem(
                    source="upwork",
                    external_id=ext,
                    url="https://www.upwork.com" + href,
                    title=clean,
                    raw_text=clean,
                ))
        return items
