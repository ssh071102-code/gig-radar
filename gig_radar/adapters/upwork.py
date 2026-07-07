import re
import httpx
from gig_radar.adapters.base import SourceAdapter
from gig_radar.models import RawItem

_JOB_RE = re.compile(r'href="(/jobs/[^"]+~[0-9a-f]+)"[^>]*>(.*?)</a>', re.S)


class UpworkBoardAdapter(SourceAdapter):
    name = "upwork"

    def __init__(self, saved_searches: list[str], timeout=15):
        self.saved_searches = saved_searches
        self.timeout = timeout

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        headers = {"User-Agent": "Mozilla/5.0 gig-radar"}
        for url in self.saved_searches:
            resp = httpx.get(url, headers=headers, timeout=self.timeout, follow_redirects=True)
            resp.raise_for_status()
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
