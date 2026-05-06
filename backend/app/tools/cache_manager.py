import csv
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import get_settings


def get_cache_key(source: str, keyword: str | None = None) -> str:
    raw_key = f"{source.strip()}::{(keyword or '').strip()}".encode("utf-8")
    return hashlib.sha256(raw_key).hexdigest()[:24]


def find_valid_cache(cache_key: str) -> dict[str, Any] | None:
    paths = _cache_paths(cache_key)
    if not paths["csv_path"].exists() or not paths["meta_path"].exists():
        return None

    metadata = _read_metadata(paths["meta_path"])
    if not metadata or _is_expired(metadata):
        _delete_cache_files(paths)
        return None

    rows = _read_csv(paths["csv_path"])
    return {
        "cache_key": cache_key,
        "csv_path": str(paths["csv_path"]),
        "metadata": metadata,
        "rows": rows,
    }


def save_csv_cache(cache_key: str, rows: list[dict[str, Any]], fieldnames: list[str], ttl_seconds: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    ttl = ttl_seconds if ttl_seconds is not None else settings.crawler_cache_ttl_seconds
    generated_at = datetime.now(UTC)
    expires_at = generated_at + timedelta(seconds=ttl)
    paths = _cache_paths(cache_key)

    paths["csv_path"].parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "cache_key": cache_key,
        "generated_at": generated_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "ttl_seconds": ttl,
        "row_count": len(rows),
        "csv_path": str(paths["csv_path"]),
    }

    rows_with_metadata = [
        {
            "生成时间": metadata["generated_at"],
            "有效期至": metadata["expires_at"],
            **row,
        }
        for row in rows
    ]
    csv_fieldnames = ["生成时间", "有效期至", *fieldnames]

    with paths["csv_path"].open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_fieldnames)
        writer.writeheader()
        writer.writerows(rows_with_metadata)

    paths["meta_path"].write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"csv_path": str(paths["csv_path"]), "metadata": metadata, "rows": rows_with_metadata}


def purge_expired_cache() -> dict[str, Any]:
    cache_dir = Path(get_settings().crawler_cache_dir)
    deleted: list[str] = []
    for meta_path in cache_dir.glob("*.meta.json"):
        metadata = _read_metadata(meta_path)
        if metadata and not _is_expired(metadata):
            continue

        cache_key = meta_path.name.replace(".meta.json", "")
        paths = _cache_paths(cache_key)
        deleted.extend(_delete_cache_files(paths))

    return {
        "tool": "crawler_cache_purge",
        "implemented": True,
        "message": f"已清理 {len(deleted)} 个过期缓存文件。",
        "deleted": deleted,
    }


def _cache_paths(cache_key: str) -> dict[str, Path]:
    cache_dir = Path(get_settings().crawler_cache_dir)
    return {
        "csv_path": cache_dir / f"{cache_key}.csv",
        "meta_path": cache_dir / f"{cache_key}.meta.json",
    }


def _read_metadata(meta_path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _is_expired(metadata: dict[str, Any]) -> bool:
    try:
        expires_at = datetime.fromisoformat(str(metadata["expires_at"]))
    except (KeyError, ValueError):
        return True
    return datetime.now(UTC) >= expires_at


def _read_csv(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def _delete_cache_files(paths: dict[str, Path]) -> list[str]:
    deleted: list[str] = []
    for path in paths.values():
        if path.exists():
            try:
                path.unlink()
                deleted.append(str(path))
            except OSError:
                continue
    return deleted
