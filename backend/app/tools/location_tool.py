from app.tools.types import tool_result


def get_location(query: str | None = None) -> dict:
    return tool_result("location", "地点工具已预留，后续接入地理位置服务。", {"query": query})

