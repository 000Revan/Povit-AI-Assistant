from pydantic import BaseModel


class KnowledgeFile(BaseModel):
    id: str
    filename: str
    file_type: str
    chunk_count: int
    vector_count: int
    upload_time: str
    file_path: str
    md5: str


class KnowledgeSummary(BaseModel):
    files: list[KnowledgeFile]
    total_files: int
    total_vectors: int

