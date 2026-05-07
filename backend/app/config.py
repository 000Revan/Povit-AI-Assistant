from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    tavily_api_key: str = ""
    tavily_base_url: str = "https://api.tavily.com"
    amap_weather_api_key: str = ""
    amap_weather_base_url: str = "https://restapi.amap.com/v3/weather/weatherInfo"
    amap_ip_api_key: str = ""
    amap_ip_base_url: str = "https://restapi.amap.com/v3/ip"
    amap_adcode_path: str = "./app/data/AMap_adcode_citycode.xlsx"
    qwen_model: str = "qwen-max"
    embedding_model: str = "text-embedding-v4"
    database_url: str = "sqlite:///./app/data/pivot_ai.db"
    upload_dir: str = "./app/data/uploads"
    chroma_dir: str = "./app/data/chroma"
    crawler_cache_dir: str = "./app/data/cache"
    crawler_cache_ttl_seconds: int = 3600
    frontend_origin: str = "http://localhost:5173"
    rag_collection_name: str = "pivot_ai_knowledge"
    chunk_size: int = 600
    chunk_overlap: int = 80
    embedding_dimensions: int = 1024
    retrieval_top_k: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def sqlite_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            return resolve_backend_path(self.database_url.replace("sqlite:///", "", 1))
        return resolve_backend_path("./app/data/pivot_ai.db")

    @property
    def resolved_upload_dir(self) -> Path:
        return resolve_backend_path(self.upload_dir)

    @property
    def resolved_chroma_dir(self) -> Path:
        return resolve_backend_path(self.chroma_dir)

    @property
    def resolved_crawler_cache_dir(self) -> Path:
        return resolve_backend_path(self.crawler_cache_dir)

    @property
    def resolved_amap_adcode_path(self) -> Path:
        return resolve_backend_path(self.amap_adcode_path)


def resolve_backend_path(path: str | Path) -> Path:
    raw_path = Path(path)
    if raw_path.is_absolute():
        return raw_path
    return BACKEND_ROOT / raw_path


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for raw_path in [
        settings.sqlite_path.parent,
        settings.resolved_upload_dir,
        settings.resolved_chroma_dir,
        settings.resolved_crawler_cache_dir,
    ]:
        raw_path.mkdir(parents=True, exist_ok=True)
    return settings
