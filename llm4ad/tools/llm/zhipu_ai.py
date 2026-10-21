from __future__ import annotations

import os
import time
from typing import Any

from zai import ZhipuAiClient

from llm4ad.base import LLM


class ZhipuAiAPI(LLM):
    @staticmethod
    def _resolve_api_key(api_key: str | None) -> str | None:
        explicit_key = str(api_key or "").strip()
        if explicit_key:
            return explicit_key
        for env_name in ("ZAI_API_KEY", "ZHIPUAI_API_KEY", "GLM_API_KEY"):
            env_value = os.getenv(env_name, "").strip()
            if env_value:
                return env_value
        return None

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "glm-5.2",
        timeout: int | float = 60,
        max_tokens: int = 1536,
        base_url: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._model = model
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._base_url = base_url

        client_kwargs: dict[str, Any] = {}
        resolved_api_key = self._resolve_api_key(api_key)
        if resolved_api_key:
            client_kwargs["api_key"] = resolved_api_key
        if base_url:
            client_kwargs["base_url"] = base_url
        client_kwargs["timeout"] = timeout
        self._client = ZhipuAiClient(**client_kwargs)

    @staticmethod
    def _normalize_messages(prompt: str | Any, **kwargs) -> list[dict[str, Any]]:
        messages_input = kwargs.get("messages")
        if messages_input is not None:
            if isinstance(messages_input, dict):
                messages = [messages_input]
            else:
                messages = list(messages_input)
        elif isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt.strip()}]
        else:
            messages = list(prompt)

        normalized = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            normalized.append(
                {
                    "role": message.get("role", "user"),
                    "content": message.get("content", message.get("message", "")),
                }
            )
        return normalized

    @staticmethod
    def _extract_message_text(response: Any) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""

        message = getattr(choices[0], "message", None)
        if message is None:
            return ""

        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content

        # GLM reasoning models may place all generated tokens into
        # `reasoning_content` when thinking is enabled or the response is cut
        # before regular content is emitted.
        reasoning_content = getattr(message, "reasoning_content", None)
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            return reasoning_content

        return ""

    def draw_sample(self, prompt: str | Any, *args, **kwargs) -> str:
        messages = self._normalize_messages(prompt, **kwargs)
        max_attempts = max(1, int(kwargs.get("empty_response_retries", 3)))
        retry_sleep = float(kwargs.get("empty_response_retry_sleep", 0.8))
        last_content = ""
        for attempt in range(max_attempts):
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=kwargs.get("temperature", 1.0),
                top_p=kwargs.get("top_p", None),
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                thinking=kwargs.get("thinking", {"type": "disabled"}),
            )
            last_content = str(self._extract_message_text(response))
            if last_content.strip():
                return last_content
            if attempt < max_attempts - 1:
                time.sleep(retry_sleep)
        return last_content
