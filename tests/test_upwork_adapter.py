import respx, httpx
from gig_radar.adapters.upwork import UpworkBoardAdapter

@respx.mock
def test_upwork_parses_titles():
    html = '<a href="/jobs/AI-bot~01ab">Build an AI bot</a>'
    respx.get("https://u/search").mock(return_value=httpx.Response(200, text=html))
    items = UpworkBoardAdapter(saved_searches=["https://u/search"]).fetch()
    assert items[0].external_id == "01ab"
    assert items[0].title == "Build an AI bot"
    assert items[0].source == "upwork"
