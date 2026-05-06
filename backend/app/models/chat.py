from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)
    stream: bool = False


class ChatResponse(BaseModel):
    session_id: str
    answer: str


class SessionCreate(BaseModel):
    title: str = "新会话"

