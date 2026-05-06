from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.graph import run_agent_graph, run_agent_graph_stream
from app.db.session_db import add_message, create_session, delete_session, list_messages, list_sessions
from app.models.chat import ChatRequest, ChatResponse, SessionCreate

router = APIRouter(tags=["chat"])


@router.get("/sessions")
def get_sessions() -> list[dict]:
    sessions = list_sessions()
    if not sessions:
        sessions.append(create_session("云端知识助手"))
    return sessions


@router.post("/sessions")
def post_session(payload: SessionCreate) -> dict:
    return create_session(payload.title)


@router.delete("/sessions/{session_id}")
def remove_session(session_id: str) -> dict[str, bool]:
    delete_session(session_id)
    return {"ok": True}


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str) -> list[dict]:
    return list_messages(session_id)


@router.post("/chat", response_model=ChatResponse)
async def post_chat(payload: ChatRequest) -> ChatResponse:
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    add_message(payload.session_id, "user", payload.message)
    history = list_messages(payload.session_id)
    result = await run_agent_graph(payload.message, history)
    add_message(payload.session_id, "assistant", result["answer"])
    return ChatResponse(session_id=payload.session_id, answer=result["answer"])


@router.post("/chat/stream")
async def post_chat_stream(payload: ChatRequest) -> StreamingResponse:
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    async def stream() -> AsyncIterator[str]:
        add_message(payload.session_id, "user", payload.message)
        history = list_messages(payload.session_id)
        answer_parts: list[str] = []
        async for chunk in run_agent_graph_stream(payload.message, history):
            answer_parts.append(chunk)
            yield chunk
        add_message(payload.session_id, "assistant", "".join(answer_parts))

    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")
