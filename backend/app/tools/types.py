from typing import Any


def tool_result(name: str, message: str, data: Any = None) -> dict:
    return {"tool": name, "implemented": False, "message": message, "data": data}

