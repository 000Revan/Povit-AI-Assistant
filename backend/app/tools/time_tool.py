from datetime import datetime, timedelta, timezone as fixed_timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Asia/Shanghai"
WEEKDAY_NAMES = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def get_current_time(timezone: str | None = None) -> dict[str, Any]:
    timezone_name = (timezone or DEFAULT_TIMEZONE).strip()
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name not in {DEFAULT_TIMEZONE, "UTC+8", "GMT+8"}:
            return _error_result(timezone_name, f"无法识别时区：{timezone_name}")
        tz = fixed_timezone(timedelta(hours=8), DEFAULT_TIMEZONE)

    now = datetime.now(tz)
    data = {
        "时区": timezone_name,
        "日期": now.strftime("%Y-%m-%d"),
        "时间": now.strftime("%H:%M:%S"),
        "星期": WEEKDAY_NAMES[now.weekday()],
        "ISO时间": now.isoformat(timespec="seconds"),
        "UTC偏移": now.strftime("%z"),
    }
    return {
        "tool": "time",
        "implemented": True,
        "query": {"timezone": timezone},
        "data": data,
        "formatted": _format_time(data),
    }


def _format_time(data: dict[str, Any]) -> str:
    return (
        "当前时间："
        f"{data['日期']} {data['时间']}，{data['星期']}，"
        f"时区：{data['时区']}，UTC偏移：{data['UTC偏移']}。"
    )


def _error_result(timezone: str, error: str) -> dict[str, Any]:
    return {
        "tool": "time",
        "implemented": False,
        "query": {"timezone": timezone},
        "data": {},
        "formatted": f"时间工具：{error}",
        "error": error,
    }
