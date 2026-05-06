from app.rag.retriever import retrieve_context


def run_rag(message: str) -> list[str]:
    return retrieve_context(message)

