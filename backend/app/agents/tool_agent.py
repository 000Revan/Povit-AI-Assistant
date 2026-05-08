from typing import Any

from app.tools.location_tool import get_location
from app.tools.crawler import get_bilibili_popular_videos, get_netease_soaring_songs
from app.tools.tavily_search import tavily_search
from app.tools.time_tool import get_current_time
from app.tools.weather import get_weather

ToolName = str
SUPPORTED_TOOLS = {
    "time",
    "ip_lookup",
    "weather",
    "bilibili_video",
    "web_search",
    "netease_soaring",
    "bilibili_popular",
}
TOOL_ALIASES = {
    "时间": "time",
    "时间获取": "time",
    "时间获取工具": "time",
    "ip": "ip_lookup",
    "IP": "ip_lookup",
    "IP地址查询": "ip_lookup",
    "IP查询工具": "ip_lookup",
    "location": "ip_lookup",
    "地点": "ip_lookup",
    "定位": "ip_lookup",
    "天气": "weather",
    "天气查询": "weather",
    "天气信息获取工具": "weather",
    "B站视频": "bilibili_video",
    "bilibili_video": "bilibili_video",
    "全网搜索": "web_search",
    "网上搜索": "web_search",
    "web": "web_search",
    "tavily": "web_search",
    "tavily_search": "web_search",
    "网易云爬虫": "netease_soaring",
    "网易云飙升榜": "netease_soaring",
    "爬虫-网易云飙升榜": "netease_soaring",
    "B站热门": "bilibili_popular",
    "B站热门爬虫": "bilibili_popular",
    "爬虫-B站热门": "bilibili_popular",
}


def decide_tools(message: str) -> list[ToolName]:
    selected: list[ToolName] = []
    if "时间" in message or "几点" in message:
        selected.append("time")
    if "天气" in message:
        selected.append("weather")
    if "IP" in message or "ip" in message or "地点" in message or "位置" in message or "地址" in message or "定位" in message:
        selected.append("ip_lookup")
    if _should_fetch_bilibili_popular(message):
        selected.append("bilibili_popular")
    elif _should_fetch_bilibili_video(message):
        selected.append("bilibili_video")
    if _should_fetch_netease_soaring(message):
        selected.append("netease_soaring")
    if _should_search(message):
        selected.append("web_search")
    return _dedupe(selected)


def normalize_tool_name(tool_name: str) -> ToolName | None:
    raw_name = str(tool_name or "").strip()
    normalized = TOOL_ALIASES.get(raw_name, raw_name)
    return normalized if normalized in SUPPORTED_TOOLS else None


def normalize_tool_names(tool_names: list[str]) -> list[ToolName]:
    selected: list[ToolName] = []
    for tool_name in tool_names:
        normalized = normalize_tool_name(tool_name)
        if normalized:
            selected.append(normalized)
    return _dedupe(selected)


def run_tools(
    message: str,
    selected_tools: list[ToolName] | None = None,
    tool_input_params: dict[str, dict[str, Any]] | None = None,
) -> list[dict]:
    selected_tools = normalize_tool_names(selected_tools) if selected_tools is not None else decide_tools(message)
    tool_input_params = tool_input_params or {}
    results: list[dict] = []
    for tool_name in selected_tools:
        results.append(run_tool(tool_name, message, tool_input_params.get(tool_name, {})))
    return results


def run_tool(tool_name: ToolName, message: str, params: dict[str, Any] | None = None) -> dict:
    params = params or {}
    normalized = normalize_tool_name(tool_name)
    if normalized == "time":
        return get_current_time(params.get("timezone"))
    if normalized == "ip_lookup":
        return get_location(params.get("ip"))
    if normalized == "weather":
        query = str(params.get("query") or message)
        return get_weather(query)
    if normalized == "bilibili_video":
        limit = int(params.get("limit") or 20)
        return get_bilibili_popular_videos(limit=limit)
    if normalized == "web_search":
        query = str(params.get("query") or message)
        max_results = int(params.get("max_results") or 3)
        return tavily_search(query, max_results=max_results)
    if normalized == "netease_soaring":
        limit = int(params.get("limit") or 100)
        return get_netease_soaring_songs(limit=limit)
    if normalized == "bilibili_popular":
        limit = int(params.get("limit") or 20)
        return get_bilibili_popular_videos(limit=limit)
    return {
        "tool": str(tool_name),
        "implemented": False,
        "query": message,
        "formatted": f"未知工具：{tool_name}",
        "error": f"unsupported_tool:{tool_name}",
    }


def _should_search(message: str) -> bool:
    search_keywords = [
        "搜索",
        "联网",
        "网上",
        "网页",
        "最新",
        "新闻",
        "Tavily",
        "tavily",
        "web",
        "Web",
    ]
    return any(keyword in message for keyword in search_keywords)


def _should_fetch_bilibili_popular(message: str) -> bool:
    bilibili_keywords = ["B站", "b站", "哔哩哔哩", "bilibili", "Bilibili"]
    popular_keywords = ["综合热门", "热门视频", "热门", "排行榜", "当前20个", "当前 20 个"]
    return any(keyword in message for keyword in bilibili_keywords) and any(keyword in message for keyword in popular_keywords)


def _should_fetch_bilibili_video(message: str) -> bool:
    bilibili_keywords = ["B站", "b站", "哔哩哔哩", "bilibili", "Bilibili"]
    video_keywords = ["视频", "视频获取", "B站视频", "b站视频"]
    return any(keyword in message for keyword in bilibili_keywords) and any(keyword in message for keyword in video_keywords)


def _should_fetch_netease_soaring(message: str) -> bool:
    netease_keywords = ["网易云", "网易云音乐", "163音乐", "NetEase", "netease"]
    soaring_keywords = ["飙升榜", "飙升", "排行榜", "榜单", "前十", "前10", "Top10", "top10"]
    return any(keyword in message for keyword in netease_keywords) and any(keyword in message for keyword in soaring_keywords)


def _dedupe(items: list[ToolName]) -> list[ToolName]:
    seen: set[ToolName] = set()
    unique: list[ToolName] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
