"""LLMClient adapter (README §6). One call()/stream() so feature code never touches
provider details. OpenAI only. API key is held in memory for the session, never persisted."""
from openai import OpenAI


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self, model: str, api_key: str, base_url: str = None):
        if not api_key:
            raise LLMError("No API key provided.")
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    def call(self, system: str, messages: list, *, temperature: float = 0.7, json_mode: bool = False) -> str:
        full_messages = ([{"role": "system", "content": system}] if system else []) + messages
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                **kwargs,
            )
        except Exception as exc:
            raise LLMError(str(exc)) from exc
        return response.choices[0].message.content or ""

    def stream(self, system: str, messages: list, *, temperature: float = 0.7):
        full_messages = ([{"role": "system", "content": system}] if system else []) + messages
        try:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            raise LLMError(str(exc)) from exc
