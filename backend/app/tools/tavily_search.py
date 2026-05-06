import httpx

from app.config import get_settings


def tavily_search(query: str, max_results: int = 1) -> dict:
    settings = get_settings()
    if not settings.tavily_api_key:
        return _error_result(query, "未配置 TAVILY_API_KEY，无法执行联网搜索。")

    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.tavily_api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(f"{settings.tavily_base_url.rstrip('/')}/search", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        return _error_result(query, f"Tavily 搜索失败：{exc}")

    results = [_normalize_result(item) for item in data.get("results", [])[:max_results]]
    formatted = format_tavily_results(results)
    return {
        "tool": "tavily_search",
        "implemented": True,
        "query": query,
        "results": results,
        "formatted": formatted,
    }


def format_tavily_results(results: list[dict]) -> str:
    if not results:
        return "Tavily 搜索结果：未检索到相关内容。"

    blocks = ["Tavily 搜索结果（3条以内）："]
    for index, item in enumerate(results, start=1):
        blocks.append(
            "\n".join(
                [
                    f"{index}. Title: {item['title']}",
                    f"   URL: {item['url']}",
                    f"   Content: {item['content']}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _normalize_result(item: dict) -> dict:
    return {
        "title": str(item.get("title") or "无标题").strip(),
        "url": str(item.get("url") or "").strip(),
        "content": str(item.get("content") or "无摘要内容").strip(),
    }


def _error_result(query: str, message: str) -> dict:
    return {
        "tool": "tavily_search",
        "implemented": False,
        "query": query,
        "results": [],
        "formatted": f"Tavily 搜索结果：{message}",
        "error": message,
    }


if __name__ == '__main__':
    print(tavily_search("agent是什么"))