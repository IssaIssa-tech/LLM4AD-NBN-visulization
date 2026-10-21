from __future__ import annotations

import http.client
import json
from typing import Any
from urllib.parse import urlparse

# Standard chat-completions suffix appended to an OpenAI-compatible base URL,
# mirroring the behaviour of the official OpenAI SDK (base_url + "/chat/completions").
_CHAT_COMPLETIONS_SUFFIX = "/chat/completions"


def normalize_thinking_param(thinking: Any) -> dict[str, str] | None:
    """Normalize a ``thinking`` request option into DeepSeek's wire shape.

    Accepts ``{"type": "enabled"|"disabled"}``, or short strings like
    ``"disabled"`` / ``"off"`` / ``"on"`` / ``"enabled"`` (the platform's
    default LLM config uses ``thinking: "disabled"`` so reasoning chains never
    leak into the EOH code parser). Returns None when unset/unknown so the
    field is omitted for providers that do not understand it.
    """
    if isinstance(thinking, dict):
        thinking_type = str(thinking.get("type", "") or "").strip().lower()
        if thinking_type in {"enabled", "disabled"}:
            return {"type": thinking_type}
        return None
    text = str(thinking or "").strip().lower()
    if text in {"disabled", "off", "false", "0", "no"}:
        return {"type": "disabled"}
    if text in {"enabled", "on", "true", "1", "yes"}:
        return {"type": "enabled"}
    return None


class OpenAICompatibleLLM:
    """Minimal, provider-agnostic OpenAI-compatible chat client.

    It works with any endpoint that exposes ``POST {base_url}/chat/completions``
    with Bearer authentication and the standard OpenAI request/response schema.
    That covers OpenAI, DeepSeek, Moonshot, Zhipu (``/api/paas/v4``), together
    with self-hosted gateways such as vLLM / Ollama's OpenAI bridge.

    The caller supplies three fields from the UI: ``base_url``, ``api_key`` and
    ``model`` -- nothing about the concrete vendor is hard-coded here.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int | float = 60,
        max_tokens: int = 1536,
        temperature: float = 1.0,
        thinking: Any = None,
        **kwargs: Any,
    ) -> None:
        self._base_url = str(base_url or "").strip()
        self._api_key = str(api_key or "").strip()
        self._model = str(model or "").strip()
        self._timeout = max(1, int(timeout))
        self._max_tokens = max(1, int(max_tokens))
        self._temperature = float(temperature)
        self._thinking = thinking
        self._extra = kwargs

    def _resolve_endpoint(self) -> tuple[bool, str, int, str]:
        parsed = urlparse(self._base_url)
        if not parsed.scheme or not parsed.netloc:
            raise RuntimeError(
                f"无效的 API Base URL: {self._base_url!r}。请填写形如 "
                "https://api.openai.com/v1 的完整地址。"
            )
        secure = parsed.scheme.lower() != "http"
        host = parsed.hostname or ""
        port = parsed.port or (443 if secure else 80)
        path = parsed.path.rstrip("/")
        request_path = path if path.endswith(_CHAT_COMPLETIONS_SUFFIX) else f"{path}{_CHAT_COMPLETIONS_SUFFIX}"
        if not request_path.startswith("/"):
            request_path = "/" + request_path
        return secure, host, port, request_path

    @staticmethod
    def _normalize_messages(prompt: str | Any, **kwargs: Any) -> list[dict[str, Any]]:
        messages_input = kwargs.get("messages")
        if messages_input is not None:
            return [messages_input] if isinstance(messages_input, dict) else list(messages_input)
        if isinstance(prompt, str):
            return [{"role": "user", "content": prompt.strip()}]
        if isinstance(prompt, dict):
            return [prompt]
        return list(prompt)

    def draw_sample(self, prompt: str | Any, *args: Any, **kwargs: Any) -> str:
        if not self._model:
            raise RuntimeError("未提供模型名称，无法调用 LLM。")
        secure, host, port, request_path = self._resolve_endpoint()
        if not host:
            raise RuntimeError(f"无法从 Base URL 解析主机名: {self._base_url!r}。")

        messages = self._normalize_messages(prompt, **kwargs)
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": int(kwargs.get("max_tokens", self._max_tokens)),
            "temperature": float(kwargs.get("temperature", self._temperature)),
            # Stream the completion so the socket read timeout applies *between
            # chunks* rather than to the whole generation. Long completions (e.g.
            # rewriting a several-hundred-line script) no longer trip the read
            # timeout as long as tokens keep arriving.
            "stream": True,
        }
        top_p = kwargs.get("top_p", self._extra.get("top_p"))
        if top_p is not None:
            body["top_p"] = top_p
        thinking = normalize_thinking_param(kwargs.get("thinking", self._thinking))
        if thinking is not None:
            body["thinking"] = thinking
        # Encode to UTF-8 bytes explicitly: http.client would otherwise try to
        # latin-1 encode a str body and blow up on non-ASCII (e.g. Chinese) prompts.
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "text/event-stream",
        }

        connection_cls = http.client.HTTPSConnection if secure else http.client.HTTPConnection
        conn = connection_cls(host, port, timeout=self._timeout)
        try:
            conn.request("POST", request_path, payload, headers)
            response = conn.getresponse()
            status = response.status
            if status < 200 or status >= 300:
                raw = response.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"LLM 接口返回 HTTP {status}: {raw[:600]}。请检查 Base URL、API Key、模型名与网络。"
                )
            content_type = (response.getheader("Content-Type") or "").lower()
            if "text/event-stream" in content_type:
                return self._read_stream(response)
            # Provider ignored stream=True and returned a single JSON body; fall
            # back to parsing it as a normal (non-streaming) completion.
            raw = response.read().decode("utf-8", errors="replace")
            return self._parse_completion(raw)
        finally:
            conn.close()

    @staticmethod
    def _extract_message_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        # Some reasoning models place output in reasoning_content when content is empty.
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning
        return str(content or "")

    def _parse_completion(self, raw: str) -> str:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"LLM 接口返回了非 JSON 内容: {raw[:600]!r}") from error
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError(f"LLM 接口响应结构异常: {json.dumps(data, ensure_ascii=False)[:600]}") from error
        return self._extract_message_text(message)

    def _read_stream(self, response: http.client.HTTPResponse) -> str:
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        error_payload = ""
        while True:
            raw_line = response.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or line.startswith(":"):
                continue  # blank separators / SSE comments (keep-alive)
            if not line.startswith("data:"):
                # Some gateways emit a JSON error object without SSE framing.
                error_payload += line
                continue
            data_str = line[len("data:"):].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            piece = delta.get("content")
            if isinstance(piece, str):
                content_parts.append(piece)
            reasoning_piece = delta.get("reasoning_content")
            if isinstance(reasoning_piece, str):
                reasoning_parts.append(reasoning_piece)
        content = "".join(content_parts)
        if content.strip():
            return content
        reasoning = "".join(reasoning_parts)
        if reasoning.strip():
            return reasoning
        if error_payload.strip():
            raise RuntimeError(f"LLM 流式响应异常: {error_payload[:600]}")
        return content

    def draw_samples(self, prompts: list[str | Any], *args: Any, **kwargs: Any) -> list[str]:
        return [self.draw_sample(prompt, *args, **kwargs) for prompt in prompts]

    def close(self) -> None:
        return None


def create_openai_compatible_llm(**kwargs: Any) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(**kwargs)
