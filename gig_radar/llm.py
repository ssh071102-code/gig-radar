import anthropic


class LLM:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, client=None):
        if client is not None:
            self.client = client
        else:
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url        # point at any Anthropic-compatible gateway
            self.client = anthropic.Anthropic(**kwargs)

    def _text(self, msg) -> str:
        # Concatenate all text blocks (skip thinking blocks and anything else without .text)
        return "".join(b.text for b in msg.content if hasattr(b, "text"))

    def complete(self, model: str, system: str, user: str, max_tokens=1500) -> str:
        # Some OpenAI/Anthropic-compatible gateways inject their own system prompt, so
        # instructions go in the user turn. Some models also reject assistant prefill,
        # so we parse a delimited text format instead of forcing JSON.
        msg = self.client.messages.create(
            model=model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": f"{system}\n\n{user}"}],
        )
        return self._text(msg)
