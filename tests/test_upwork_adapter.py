import httpx
import respx

from gig_radar.adapters.upwork import UpworkBoardAdapter


@respx.mock
def test_upwork_parses_titles():
    html = '<a href="/jobs/AI-bot~01ab">Build an AI bot</a>'
    respx.get("https://u/search").mock(return_value=httpx.Response(200, text=html))
    items = UpworkBoardAdapter(saved_searches=["https://u/search"]).fetch()
    assert items[0].external_id == "01ab"
    assert items[0].title == "Build an AI bot"
    assert items[0].source == "upwork"


@respx.mock
def test_upwork_blocked_search_is_isolated(caplog):
    import logging
    html = '<a href="/jobs/AI-bot~01ab">Build an AI bot</a>'
    respx.get("https://u/blocked").mock(return_value=httpx.Response(403))   # Cloudflare says no
    respx.get("https://u/ok").mock(return_value=httpx.Response(200, text=html))
    with caplog.at_level(logging.WARNING, logger="gig_radar"):
        items = UpworkBoardAdapter(saved_searches=["https://u/blocked", "https://u/ok"]).fetch()
    assert [i.external_id for i in items] == ["01ab"]    # the healthy search still yields
    assert any("Upwork search failed" in r.message for r in caplog.records)
