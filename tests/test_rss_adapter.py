import logging
from pathlib import Path
import respx
import httpx
from gig_radar.adapters.rss import RssAdapter

FIX = Path(__file__).parent / "fixtures" / "sample_rss.xml"

def test_rss_parses_items():
    items = RssAdapter(feeds=[FIX.as_uri()]).fetch()
    assert len(items) == 1
    it = items[0]
    assert it.source == "rss"
    assert it.external_id == "https://example.com/job/1"
    assert "AI automation" in it.title
    assert it.url == "https://example.com/job/1"

def test_rss_skips_entries_without_link():
    fix = Path(__file__).parent / "fixtures" / "rss_missing_link.xml"
    items = RssAdapter(feeds=[fix.as_uri()]).fetch()
    assert len(items) == 1                          # the linkless entry is skipped, not a crash
    assert items[0].url == "https://example.com/ok"

def test_rss_logs_on_bad_feed(caplog):
    fix = Path(__file__).parent / "fixtures" / "bad_rss.xml"
    with caplog.at_level(logging.WARNING, logger="gig_radar"):
        items = RssAdapter(feeds=[fix.as_uri()]).fetch()
    assert items == []
    assert any("possibly failed" in r.message for r in caplog.records)

def test_rss_keyword_filter():
    fix = Path(__file__).parent / "fixtures" / "rss_keywords.xml"
    items = RssAdapter(feeds=[fix.as_uri()], keywords=["AI", "LLM"]).fetch()
    assert len(items) == 1                       # only the keyword hit survives
    assert "AI" in items[0].title

@respx.mock
def test_rss_http_uses_browser_ua():
    rss = ('<?xml version="1.0"?><rss version="2.0"><channel>'
           '<item><title>AI job</title><link>https://x/1</link><description>LLM</description></item>'
           '</channel></rss>')
    route = respx.get("https://feed.test/rss").mock(return_value=httpx.Response(200, text=rss))
    items = RssAdapter(feeds=["https://feed.test/rss"], keywords=["AI"]).fetch()
    assert len(items) == 1 and items[0].url == "https://x/1"
    assert "Mozilla" in route.calls[0].request.headers["user-agent"]   # sent a browser UA

@respx.mock
def test_rss_multi_http_feeds_no_delay():
    rss = ('<?xml version="1.0"?><rss version="2.0"><channel>'
           '<item><title>AI a</title><link>https://x/1</link><description>LLM</description></item>'
           '</channel></rss>')
    respx.get("https://f1/rss").mock(return_value=httpx.Response(200, text=rss))
    respx.get("https://f2/rss").mock(return_value=httpx.Response(200, text=rss.replace("x/1","x/2")))
    items = RssAdapter(feeds=["https://f1/rss", "https://f2/rss"],
                       keywords=["AI"], request_delay=0).fetch()
    assert {i.url for i in items} == {"https://x/1", "https://x/2"}   # both feeds were fetched
