from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.db.knowledge_db import add_file, delete_file, get_file, list_files
from app.models.knowledge import KnowledgeSummary
from app.rag.chunker import split_text
from app.rag.vector_store import add_documents, delete_documents
from app.utils.file_utils import extract_text, validate_upload
from app.utils.md5_utils import file_md5

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge/files", response_model=KnowledgeSummary)
def files() -> KnowledgeSummary:
    items = list_files()
    return KnowledgeSummary(
        files=items,
        total_files=len(items),
        total_vectors=sum(item["vector_count"] for item in items),
    )


@router.post("/knowledge/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    try:
        file_type = validate_upload(file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target = Path(get_settings().upload_dir) / f"{uuid4()}_{file.filename}"
    content = await file.read()
    target.write_bytes(content)
    text = extract_text(target)
    chunks = split_text(text)
    if not chunks:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="未能从文件中提取可入库文本")
    md5 = file_md5(target)
    record = add_file(file.filename or target.name, file_type, str(target), md5, len(chunks))
    vector_count = add_documents(record["id"], chunks, {"filename": record["filename"], "file_type": file_type})
    record["vector_count"] = vector_count
    return record


@router.post("/knowledge/confirm")
def confirm() -> dict[str, bool]:
    return {"ok": True}


@router.delete("/knowledge/files/{file_id}")
def remove_file(file_id: str) -> dict[str, bool]:
    record = get_file(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="文件不存在")
    delete_documents(file_id)
    delete_file(file_id)
    path = Path(record["file_path"])
    if path.exists():
        path.unlink()
    return {"ok": True}
