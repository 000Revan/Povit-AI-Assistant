import json
from collections.abc import AsyncIterator

import httpx

from app.config import get_settings


def _chat_payload(messages: list[dict[str, str]], stream: bool = False) -> dict:
    settings = get_settings()
    return {
        "model": settings.qwen_model,
        "messages": messages,
        "temperature": 0.4,
        "stream": stream,
    }


def _headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is empty")
    return {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
        "Content-Type": "application/json",
    }


async def chat_completion(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    url = f"{settings.dashscope_base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=_chat_payload(messages), headers=_headers())
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


async def stream_chat_completion(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    settings = get_settings()
    url = f"{settings.dashscope_base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, json=_chat_payload(messages, stream=True), headers=_headers()) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line.removeprefix("data:").strip()
                if line == "[DONE]":
                    break
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = payload.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
