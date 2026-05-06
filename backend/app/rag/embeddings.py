import hashlib
import math
from typing import Iterable

import httpx

from app.config import get_settings


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    text_list = list(texts)
    if not text_list:
        return []
    try:
        return _dashscope_embeddings(text_list)
    except Exception:
        return [_fallback_embedding(text) for text in text_list]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def _dashscope_embeddings(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is empty")

    url = f"{settings.dashscope_base_url.rstrip('/')}/embeddings"
    payload = {
        "model": settings.embedding_model,
        "input": texts,
        "dimensions": settings.embedding_dimensions,
        "encoding_format": "float",
    }
    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=15) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return [item["embedding"] for item in sorted(data["data"], key=lambda item: item["index"])]


def _fallback_embedding(text: str) -> list[float]:
    settings = get_settings()
    dimensions = settings.embedding_dimensions
    vector = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    words = [word for word in lowered.split() if word]
    chars = [char for char in lowered if "\u4e00" <= char <= "\u9fff"]
    bigrams = [lowered[index : index + 2] for index in range(max(len(lowered) - 1, 0))]
    return words + chars + bigrams
