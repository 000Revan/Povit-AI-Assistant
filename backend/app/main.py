from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.knowledge_db import init_knowledge_db
from app.db.session_db import init_session_db
from app.routers import chat, knowledge


def create_app() -> FastAPI:
    settings = get_settings()
    init_session_db()
    init_knowledge_db()

    app = FastAPI(title="Pivot AI Assistant", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat.router, prefix="/api")
    app.include_router(knowledge.router, prefix="/api")
    return app


app = create_app()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

