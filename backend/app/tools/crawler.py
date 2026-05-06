from typing import Any

import httpx

from app.config import get_settings
from app.tools.cache_manager import find_valid_cache, get_cache_key, purge_expired_cache, save_csv_cache

BILIBILI_POPULAR_URL = "https://api.bilibili.com/x/web-interface/popular"
BILIBILI_VIDEO_URL = "https://www.bilibili.com/video/{bvid}"
NETEASE_SOARING_URL = "https://music.163.com/api/playlist/detail?id=19723756"
NETEASE_SONG_URL = "https://music.163.com/#/song?id={song_id}"
BILIBILI_POPULAR_FIELDNAMES = [
    "排名",
    "分区",
    "标题",
    "简介",
    "时长(秒)",
    "UP主ID",
    "UP主名称",
    "播放量",
    "弹幕数",
    "评论数",
    "收藏数",
    "投币数",
    "分享数",
    "点赞数",
    "发布地点",
    "BV号",
    "AV号",
    "视频链接",
]
NETEASE_SOARING_FIELDNAMES = [
    "排名",
    "歌名",
    "歌手",
    "专辑",
    "时长",
    "歌曲ID",
    "歌曲链接",
]


def get_bilibili_popular_videos(limit: int = 20, force_refresh: bool = False) -> dict[str, Any]:
    limit = max(1, min(limit, 50))
    settings = get_settings()
    cache_key = get_cache_key("bilibili_popular", keyword=str(limit))
    purge_expired_cache()

    if not force_refresh:
        cached = find_valid_cache(cache_key)
        if cached:
            return _success_result(cached["rows"], cached["csv_path"], cached["metadata"], cache_hit=True)

    try:
        rows = _fetch_bilibili_popular(limit)
    except Exception as exc:
        return {
            "tool": "bilibili_popular_crawler",
            "implemented": False,
            "message": f"B站综合热门视频爬取失败：{exc}",
            "cache_hit": False,
            "csv_path": "",
            "metadata": {},
            "rows": [],
            "formatted": f"B站综合热门视频爬取失败：{exc}",
            "error": str(exc),
        }
    cached = save_csv_cache(
        cache_key,
        rows,
        BILIBILI_POPULAR_FIELDNAMES,
        ttl_seconds=settings.crawler_cache_ttl_seconds,
    )
    return _success_result(cached["rows"], cached["csv_path"], cached["metadata"], cache_hit=False)


def get_netease_soaring_songs(limit: int = 100, force_refresh: bool = False) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    settings = get_settings()
    cache_key = get_cache_key("netease_soaring", keyword=str(limit))
    purge_expired_cache()

    if not force_refresh:
        cached = find_valid_cache(cache_key)
        if cached:
            return _netease_success_result(cached["rows"], cached["csv_path"], cached["metadata"], cache_hit=True)

    try:
        rows = _fetch_netease_soaring(limit)
    except Exception as exc:
        return {
            "tool": "netease_soaring_crawler",
            "implemented": False,
            "message": f"网易云音乐飙升榜爬取失败：{exc}",
            "cache_hit": False,
            "csv_path": "",
            "metadata": {},
            "rows": [],
            "formatted": f"网易云音乐飙升榜爬取失败：{exc}",
            "error": str(exc),
        }

    cached = save_csv_cache(
        cache_key,
        rows,
        NETEASE_SOARING_FIELDNAMES,
        ttl_seconds=settings.crawler_cache_ttl_seconds,
    )
    return _netease_success_result(cached["rows"], cached["csv_path"], cached["metadata"], cache_hit=False)


def crawl_to_csv(url: str = BILIBILI_POPULAR_URL, keyword: str | None = None) -> dict[str, Any]:
    if "bilibili.com" in url or keyword in {None, "bilibili_popular", "B站综合热门"}:
        return get_bilibili_popular_videos(limit=20)
    if "music.163.com" in url or keyword in {"netease_soaring", "网易云飙升榜"}:
        return get_netease_soaring_songs(limit=100)
    return {
        "tool": "crawler",
        "implemented": False,
        "message": "当前仅支持 B站综合热门视频爬虫和网易云音乐飙升榜爬虫。",
        "data": {"url": url, "keyword": keyword},
    }


def _fetch_bilibili_popular(limit: int) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
    }
    params = {"ps": limit, "pn": 1}

    with httpx.Client(timeout=20, headers=headers) as client:
        response = client.get(BILIBILI_POPULAR_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    if payload.get("code") != 0:
        raise RuntimeError(f"B站热门接口返回异常：{payload.get('message') or payload}")

    items = payload.get("data", {}).get("list", [])
    return [_normalize_bilibili_item(item, index) for index, item in enumerate(items[:limit], start=1)]


def _normalize_bilibili_item(item: dict[str, Any], rank: int) -> dict[str, Any]:
    owner = item.get("owner") or {}
    stat = item.get("stat") or {}
    bvid = str(item.get("bvid") or "").strip()
    return {
        "排名": rank,
        "分区": _clean_text(item.get("tname")),
        "标题": _clean_text(item.get("title")),
        "简介": _clean_text(item.get("desc")),
        "时长(秒)": item.get("duration") or 0,
        "UP主ID": owner.get("mid") or "",
        "UP主名称": _clean_text(owner.get("name")),
        "播放量": stat.get("view") or 0,
        "弹幕数": stat.get("danmaku") or 0,
        "评论数": stat.get("reply") or 0,
        "收藏数": stat.get("favorite") or 0,
        "投币数": stat.get("coin") or 0,
        "分享数": stat.get("share") or 0,
        "点赞数": stat.get("like") or 0,
        "发布地点": _clean_text(item.get("pub_location")),
        "BV号": bvid,
        "AV号": item.get("aid") or "",
        "视频链接": BILIBILI_VIDEO_URL.format(bvid=bvid) if bvid else "",
    }


def _fetch_netease_soaring(limit: int) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://music.163.com/",
        "Accept": "application/json, text/plain, */*",
    }

    with httpx.Client(timeout=20, headers=headers) as client:
        response = client.get(NETEASE_SOARING_URL)
        response.raise_for_status()
        payload = response.json()

    if payload.get("code") != 200:
        raise RuntimeError(f"网易云音乐接口返回异常：{payload.get('message') or payload}")

    items = payload.get("result", {}).get("tracks", [])
    return [_normalize_netease_song(item, index) for index, item in enumerate(items[:limit], start=1)]


def _normalize_netease_song(item: dict[str, Any], rank: int) -> dict[str, Any]:
    song_id = item.get("id") or ""
    artists = item.get("artists") or []
    album = item.get("album") or {}
    duration = item.get("duration") or 0
    return {
        "排名": rank,
        "歌名": _clean_text(item.get("name")),
        "歌手": "/".join(_clean_text(artist.get("name")) for artist in artists if artist.get("name")),
        "专辑": _clean_text(album.get("name")),
        "时长": _format_duration(duration),
        "歌曲ID": song_id,
        "歌曲链接": NETEASE_SONG_URL.format(song_id=song_id) if song_id else "",
    }


def _format_duration(duration_ms: int) -> str:
    total_seconds = duration_ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _clean_text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _success_result(rows: list[dict[str, Any]], csv_path: str, metadata: dict[str, Any], cache_hit: bool) -> dict[str, Any]:
    source = "缓存" if cache_hit else "实时爬取"
    return {
        "tool": "bilibili_popular_crawler",
        "implemented": True,
        "message": f"已通过{source}获取 B站综合热门视频数据，共 {len(rows)} 条，CSV：{csv_path}",
        "cache_hit": cache_hit,
        "csv_path": csv_path,
        "metadata": metadata,
        "rows": rows,
        "formatted": _format_bilibili_rows(rows, csv_path, metadata, cache_hit),
    }


def _format_bilibili_rows(rows: list[dict[str, Any]], csv_path: str, metadata: dict[str, Any], cache_hit: bool) -> str:
    source = "缓存命中" if cache_hit else "重新爬取"
    lines = [
        f"B站综合热门视频（{source}）：",
        f"CSV: {csv_path}",
        f"生成时间: {metadata.get('generated_at', '')}",
        f"有效期至: {metadata.get('expires_at', '')}",
        "Top 20:",
    ]
    for row in rows[:20]:
        lines.append(
            f"{row.get('排名')}. {row.get('标题')} | UP: {row.get('UP主名称')} | "
            f"播放: {row.get('播放量')} | 点赞: {row.get('点赞数')} | {row.get('视频链接')}"
        )
    return "\n".join(lines)


def _netease_success_result(rows: list[dict[str, Any]], csv_path: str, metadata: dict[str, Any], cache_hit: bool) -> dict[str, Any]:
    source = "缓存" if cache_hit else "实时爬取"
    return {
        "tool": "netease_soaring_crawler",
        "implemented": True,
        "message": f"已通过{source}获取网易云音乐飙升榜数据，共 {len(rows)} 条，CSV：{csv_path}",
        "cache_hit": cache_hit,
        "csv_path": csv_path,
        "metadata": metadata,
        "rows": rows,
        "formatted": _format_netease_rows(rows, csv_path, metadata, cache_hit),
    }


def _format_netease_rows(rows: list[dict[str, Any]], csv_path: str, metadata: dict[str, Any], cache_hit: bool) -> str:
    source = "缓存命中" if cache_hit else "重新爬取"
    lines = [
        f"网易云音乐飙升榜 Top 100（{source}）：",
        f"CSV: {csv_path}",
        f"生成时间: {metadata.get('generated_at', '')}",
        f"有效期至: {metadata.get('expires_at', '')}",
        "前十首:",
    ]
    for row in rows[:10]:
        lines.append(
            f"{row.get('排名')}. {row.get('歌名')} | 歌手: {row.get('歌手')} | "
            f"专辑: {row.get('专辑')} | 时长: {row.get('时长')} | {row.get('歌曲链接')}"
        )
    return "\n".join(lines)
