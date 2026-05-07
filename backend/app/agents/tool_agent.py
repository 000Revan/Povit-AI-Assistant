from app.tools.location_tool import get_location
from app.tools.crawler import get_bilibili_popular_videos, get_netease_soaring_songs
from app.tools.tavily_search import tavily_search
from app.tools.time_tool import get_current_time
from app.tools.weather import get_weather

ToolName = str


def decide_tools(message: str) -> list[ToolName]:
    selected: list[ToolName] = []
    if "时间" in message or "几点" in message:
        selected.append("time")
    if "天气" in message:
        selected.append("weather")
    if "地点" in message or "位置" in message or "地址" in message or "定位" in message:
        selected.append("location")
    if _should_fetch_bilibili_popular(message):
        selected.append("bilibili_popular")
    if _should_fetch_netease_soaring(message):
        selected.append("netease_soaring")
    if _should_search(message):
        selected.append("tavily_search")
    return _dedupe(selected)


def run_tools(message: str, selected_tools: list[ToolName] | None = None) -> list[dict]:
    selected_tools = selected_tools if selected_tools is not None else decide_tools(message)
    results: list[dict] = []
    if "time" in selected_tools:
        results.append(get_current_time())
    if "weather" in selected_tools:
        results.append(get_weather(message))
    if "location" in selected_tools:
        results.append(get_location())
    if "bilibili_popular" in selected_tools:
        results.append(get_bilibili_popular_videos(limit=20))
    if "netease_soaring" in selected_tools:
        results.append(get_netease_soaring_songs(limit=100))
    if "tavily_search" in selected_tools:
        results.append(tavily_search(message, max_results=3))
    return results


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
