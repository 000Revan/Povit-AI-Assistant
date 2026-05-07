from typing import Any

import httpx

from app.config import get_settings

LOCATION_FIELD_NAMES = {
    "province": "省份",
    "city": "城市",
    "adcode": "区域编码",
    "rectangle": "所在城市矩形区域",
}


def get_location(ip: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    api_key = settings.amap_ip_api_key or settings.amap_weather_api_key
    if not api_key:
        return _error_result("未配置 AMAP_IP_API_KEY，无法查询高德 IP 定位。", ip=ip)

    params = {"output": "JSON", "key": api_key}
    if ip:
        params["ip"] = ip

    try:
        payload = _fetch_location_payload(settings.amap_ip_base_url, params)
    except Exception as exc:
        return _error_result(f"高德 IP 定位请求失败：{exc}", ip=ip)

    if payload.get("status") != "1":
        error = payload.get("info") or payload.get("infocode") or "未知错误"
        return _error_result(f"高德 IP 定位接口返回异常：{error}", ip=ip)

    data = _normalize_location_payload(payload)
    return {
        "tool": "location",
        "implemented": True,
        "query": {"ip": ip},
        "data": data,
        "formatted": _format_location(data),
    }


def _fetch_location_payload(url: str, params: dict[str, str]) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.TransportError as exc:
        if "SSL" not in str(exc).upper():
            raise

    with httpx.Client(timeout=15, verify=False) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _normalize_location_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        chinese_key: payload.get(raw_key) or ""
        for raw_key, chinese_key in LOCATION_FIELD_NAMES.items()
    }


def _format_location(data: dict[str, Any]) -> str:
    details = "，".join(f"{key}：{value}" for key, value in data.items() if value)
    return f"高德 IP 定位结果：{details or '未获取到有效定位信息'}"


def _error_result(error: str, ip: str | None = None) -> dict[str, Any]:
    return {
        "tool": "location",
        "implemented": False,
        "query": {"ip": ip},
        "data": {},
        "formatted": f"高德 IP 定位工具：{error}",
        "error": error,
    }
