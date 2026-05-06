from app.tools.types import tool_result


def get_current_time(timezone: str | None = None) -> dict:
    return tool_result("time", "时间工具已预留，后续补充真实时间处理。", {"timezone": timezone})

