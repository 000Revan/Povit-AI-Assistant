import json
from pathlib import Path

from app.config import get_settings
from app.rag.embeddings import embed_query, embed_texts


def _store_path() -> Path:
    path = Path(get_settings().chroma_dir) / "fallback_vectors.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load() -> list[dict]:
    path = _store_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save(items: list[dict]) -> None:
    _store_path().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def add_documents(file_id: str, chunks: list[str], metadata: dict) -> int:
    if not chunks:
        return 0
    try:
        return _add_chroma_documents(file_id, chunks, metadata)
    except Exception:
        return _add_fallback_documents(file_id, chunks, metadata)


def delete_documents(file_id: str) -> None:
    try:
        _collection().delete(where={"file_id": file_id})
    except Exception:
        pass
    _save([item for item in _load() if item["file_id"] != file_id])


def similarity_search(query: str, limit: int | None = None) -> list[dict]:
    top_k = limit or get_settings().retrieval_top_k
    try:
        return _chroma_similarity_search(query, top_k)
    except Exception:
        return _fallback_similarity_search(query, top_k)


def _add_chroma_documents(file_id: str, chunks: list[str], metadata: dict) -> int:
    collection = _collection()
    ids = [f"{file_id}:{index}" for index in range(len(chunks))]
    metadatas = [
        {
            **metadata,
            "file_id": file_id,
            "chunk_id": f"{file_id}:{index}",
            "chunk_index": index,
        }
        for index in range(len(chunks))
    ]
    collection.add(ids=ids, documents=chunks, metadatas=metadatas, embeddings=embed_texts(chunks))
    return len(chunks)


def _add_fallback_documents(file_id: str, chunks: list[str], metadata: dict) -> int:
    items = [item for item in _load() if item["file_id"] != file_id]
    embeddings = embed_texts(chunks)
    for index, content in enumerate(chunks):
        items.append(
            {
                "id": f"{file_id}:{index}",
                "file_id": file_id,
                "chunk_index": index,
                "content": content,
                "metadata": metadata,
                "embedding": embeddings[index],
            }
        )
    _save(items)
    return len(chunks)


def _chroma_similarity_search(query: str, limit: int) -> list[dict]:
    results = _collection().query(
        query_embeddings=[embed_query(query)],
        n_results=limit,
        include=["documents", "metadatas", "distances"],
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    items: list[dict] = []
    for index, content in enumerate(documents):
        metadata = metadatas[index] or {}
        distance = distances[index] if index < len(distances) else 0
        items.append(
            {
                "id": metadata.get("chunk_id"),
                "file_id": metadata.get("file_id"),
                "chunk_index": metadata.get("chunk_index", 0),
                "content": content,
                "metadata": metadata,
                "score": 1 / (1 + distance),
            }
        )
    return items


def _fallback_similarity_search(query: str, limit: int) -> list[dict]:
    query_embedding = embed_query(query)
    scored: list[tuple[float, dict]] = []
    for item in _load():
        score = _cosine_similarity(query_embedding, item.get("embedding", []))
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    results: list[dict] = []
    for score, item in scored[:limit]:
        result = {key: value for key, value in item.items() if key != "embedding"}
        result["score"] = score
        results.append(result)
    return results


def _collection():
    import chromadb

    settings = get_settings()
    client = chromadb.PersistentClient(path=settings.chroma_dir)
    return client.get_or_create_collection(name=settings.rag_collection_name)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
