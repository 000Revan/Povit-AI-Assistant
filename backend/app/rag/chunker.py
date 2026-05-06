from app.config import get_settings


SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", ";", ".", " ", ""]


def split_text(text: str, chunk_size: int | None = None, chunk_overlap: int | None = None) -> list[str]:
    settings = get_settings()
    size = chunk_size or settings.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
    clean_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not clean_text:
        return []

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            separators=SEPARATORS,
        )
        return [chunk for chunk in splitter.split_text(clean_text) if chunk.strip()]
    except Exception:
        return _fallback_split(clean_text, size, overlap)


def _fallback_split(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks

