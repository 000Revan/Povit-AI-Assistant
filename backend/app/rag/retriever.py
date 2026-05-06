from app.rag.vector_store import similarity_search


def retrieve_context(question: str) -> list[str]:
    contexts: list[str] = []
    for item in similarity_search(question):
        metadata = item.get("metadata") or {}
        filename = metadata.get("filename", "未知文件")
        chunk_index = item.get("chunk_index", metadata.get("chunk_index", 0))
        score = item.get("score", 0)
        contexts.append(f"来源：{filename} / chunk {chunk_index} / score {score:.3f}\n{item['content']}")
    return contexts
