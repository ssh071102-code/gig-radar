from types import SimpleNamespace
from gig_radar.llm import LLM


def _client(text):
    msg = SimpleNamespace(content=[SimpleNamespace(text=text)])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: msg))


def test_complete_returns_text():
    llm = LLM(client=_client("hello world"))
    assert llm.complete("m", "s", "u") == "hello world"


def test_complete_joins_text_blocks_skips_thinking():
    msg = SimpleNamespace(content=[
        SimpleNamespace(text="a"), SimpleNamespace(thinking="skip"), SimpleNamespace(text="b")])
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: msg))
    assert LLM(client=client).complete("m", "s", "u") == "ab"


def test_llm_passes_base_url():
    llm = LLM(api_key="k", base_url="https://proxy.test")
    assert "proxy.test" in str(llm.client.base_url)


def test_llm_no_base_url_defaults():
    llm = LLM(api_key="k")
    assert llm.client.base_url is not None
