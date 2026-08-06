"""JetLinks 设备控制函数。"""

import asyncio
import json
import os
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.logger import setup_logging
from plugins_func.register import Action, ActionResponse, ToolType, register_function

if TYPE_CHECKING:
    from core.connection import ConnectionHandler


TAG = __name__
logger = setup_logging()

ALL_PROPERTY_IDS = [
    "tds",
    "temp",
    "liquid_level",
    "light_on",
    "light_color",
    "light_brightness",
    "fan_on",
    "fan_gear",
    "filter_on",
    "filter_gear",
    "wave_on",
    "wave_gear",
    "usb_power_on",
    "oxygen_on",
    "child_lock_enable",
]

PROPERTY_SCHEMA = {
    "light_on": {"name": "照明", "type": "boolean"},
    "light_brightness": {"name": "照明亮度", "type": "int", "range": [0, 100], "step": 10},
    "fan_on": {"name": "风扇", "type": "boolean"},
    "fan_gear": {"name": "风扇挡位", "type": "int", "range": [1, 3]},
    "filter_on": {"name": "过滤", "type": "boolean"},
    "filter_gear": {"name": "过滤挡位", "type": "int", "range": [1, 3]},
    "wave_on": {"name": "造浪", "type": "boolean"},
    "wave_gear": {"name": "造浪挡位", "type": "int", "range": [1, 3]},
    "usb_power_on": {"name": "USB 供电", "type": "boolean"},
    "oxygen_on": {"name": "增氧", "type": "boolean"},
    "child_lock_enable": {"name": "童锁", "type": "boolean"},
    "light_color": {"name": "照明颜色", "type": "color_hex"},
}


def get_jetlinks_device_id(client_id: str | None) -> str | None:
    """根据小智客户端 ID 查询 JetLinks device_id。

    TODO: 在此实现 client_id 到 JetLinks device_id 的映射。
    """
    return os.getenv("JETLINKS_DEBUG_DEVICE_ID")


def _get_api_config(conn: "ConnectionHandler") -> tuple[str | None, str | None]:
    """读取服务端内部 JetLinks 配置，不使用插件调用参数。"""
    endpoint = conn.config.get("JETLINKS_ENDPOINT") or os.getenv("JETLINKS_ENDPOINT")
    token = conn.config.get("JETLINKS_TOKEN") or os.getenv("JETLINKS_TOKEN")
    return endpoint.rstrip("/") if endpoint else None, token


def _validate_value(property_id: str, value: str | int) -> tuple[bool, str]:
    schema = PROPERTY_SCHEMA.get(property_id)
    if schema is None:
        return False, f"未知属性 '{property_id}'。"

    if schema["type"] == "boolean" and str(value).lower() not in {"true", "false"}:
        return False, f"'{property_id}' 是开关属性，值必须为字符串 'true' 或 'false'。"

    if schema["type"] == "int":
        try:
            numeric_value = int(value)
        except (TypeError, ValueError):
            return False, f"'{property_id}' 需要整数值。"
        minimum, maximum = schema["range"]
        if not minimum <= numeric_value <= maximum:
            return False, f"'{property_id}' 的值必须在 {minimum} 到 {maximum} 之间。"
        step = schema.get("step")
        if step and (numeric_value - minimum) % step:
            return False, f"'{property_id}' 的值必须以 {step} 为步进。"

    if schema["type"] == "color_hex":
        color = str(value).strip().lower().removeprefix("#").removeprefix("0x")
        if len(color) != 6 or any(char not in "0123456789abcdef" for char in color):
            return False, f"'{property_id}' 需要 6 位十六进制颜色值，例如 'ff0000'。"

    return True, ""


def _to_response(result: dict[str, Any]) -> ActionResponse:
    return ActionResponse(Action.REQLLM, json.dumps(result, ensure_ascii=False), None)


async def _request(
    conn: "ConnectionHandler",
    method: str,
    path: str,
    *,
    payload: dict | None = None,
) -> dict[str, Any]:
    if not conn.client_id:
        return {"success": False, "error": "无法获取客户端 client_id。"}

    device_id = get_jetlinks_device_id(conn.client_id)
    if not device_id:
        return {
            "success": False,
            "error": "未找到该客户端对应的 JetLinks 设备。请实现 get_jetlinks_device_id。",
        }

    endpoint, token = _get_api_config(conn)
    if not endpoint or not token:
        return {"success": False, "error": "JetLinks endpoint 或 token 未配置。"}

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "X-Access-Token": token,
    }
    url = f"{endpoint}{path.format(device_id=device_id)}"
    return await asyncio.to_thread(_send_request, method, url, headers, payload)


def _send_request(
    method: str, url: str, headers: dict[str, str], payload: dict | None
) -> dict[str, Any]:
    try:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=data, headers=headers, method=method)
        with urlopen(request, timeout=10) as response:
            response_text = response.read().decode("utf-8")
        try:
            body: Any = json.loads(response_text)
        except ValueError:
            body = response_text
        return {"success": True, "body": body}
    except HTTPError as error:
        error.read()  # 消耗响应体，但不向模型或用户透传接口原始内容。
        return {
            "success": False,
            "error": f"JetLinks 请求失败（HTTP {error.code}）。",
        }
    except URLError as error:
        logger.bind(tag=TAG).error(f"JetLinks 请求失败: {error}")
        return {"success": False, "error": str(error.reason)}
    except OSError as error:
        logger.bind(tag=TAG).error(f"JetLinks 请求失败: {error}")
        return {"success": False, "error": str(error)}


set_device_property_function_desc = {
    "type": "function",
    "function": {
        "name": "set_device_property",
        "description": "控制鱼缸设备属性。可控制照明、亮度、风扇、过滤、造浪、USB供电、增氧、童锁和灯光颜色。开关值必须传字符串 'true' 或 'false'。",
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "enum": list(PROPERTY_SCHEMA), "description": "要控制的属性 ID。"},
                "value": {"type": ["string", "integer"], "description": "属性目标值。"},
            },
            "required": ["property_id", "value"],
        },
    },
}


@register_function("set_device_property", set_device_property_function_desc, ToolType.IOT_CTL)
async def set_device_property(conn: "ConnectionHandler", property_id: str, value: str | int):
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    valid, error = _validate_value(property_id, value)
    if not valid:
        return _to_response({"success": False, "property_id": property_id, "value": value, "error": error})

    if PROPERTY_SCHEMA[property_id]["type"] == "color_hex":
        color = str(value).strip().lower().removeprefix("#").removeprefix("0x")
        value = int(color, 16)

    result = await _request(
        conn,
        "PUT",
        "/device-instance/{device_id}/property",
        payload={property_id: value},
    )
    property_name = PROPERTY_SCHEMA[property_id]["name"]
    if result["success"]:
        return _to_response({"success": True, "message": f"{property_name}设置成功。"})
    return _to_response(
        {"success": False, "error": result.get("error", f"{property_name}设置失败。")}
    )


get_device_properties_function_desc = {
    "type": "function",
    "function": {
        "name": "get_device_properties",
        "description": "查询鱼缸的传感器读数与设备状态，例如水质、水温、水位、照明、风扇、过滤和增氧状态。未传 property_ids 时查询全部属性。",
        "parameters": {
            "type": "object",
            "properties": {
                "property_ids": {"type": "array", "items": {"type": "string", "enum": ALL_PROPERTY_IDS}, "description": "要查询的属性 ID 列表。"},
            },
        },
    },
}


@register_function("get_device_properties", get_device_properties_function_desc, ToolType.IOT_CTL)
async def get_device_properties(conn: "ConnectionHandler", property_ids: list[str] | None = None):
    ids_to_query = property_ids or ALL_PROPERTY_IDS
    properties: dict[str, Any] = {}
    payload = {"pageSize": 1, "pageIndex": 0, "sorts": [{"name": "timestamp", "order": "desc"}]}

    for property_id in ids_to_query:
        if property_id not in ALL_PROPERTY_IDS:
            properties[property_id] = {"error": "未知属性"}
            continue
        result = await _request(
            conn,
            "POST",
            f"/device/instance/{{device_id}}/property/{property_id}/_query",
            payload=payload,
        )
        if not result["success"]:
            properties[property_id] = {"error": result.get("error", "JetLinks 查询失败。")}
            continue
        body = result["body"]
        if not isinstance(body, dict) or body.get("status") != 200:
            properties[property_id] = {"error": body.get("message", "JetLinks 查询失败") if isinstance(body, dict) else "JetLinks 返回格式错误"}
            continue
        data = body.get("result", {}).get("data", []) if isinstance(body, dict) else []
        if data:
            record = data[0]
            properties[property_id] = {
                "value": record.get("value"),
                "formatValue": record.get("formatValue"),
                "propertyName": record.get("propertyName"),
            }
        else:
            properties[property_id] = None

    return _to_response({"success": True, "properties": properties})


def _function_desc(name: str, description: str, parameters: dict | None = None) -> dict:
    function = {"name": name, "description": description, "parameters": {"type": "object", "properties": {}}}
    if parameters:
        function["parameters"] = parameters
    return {"type": "function", "function": function}


async def _invoke_device_function(
    conn: "ConnectionHandler", function_id: str, payload: dict | None = None
) -> ActionResponse:
    result = await _request(
        conn,
        "POST",
        f"/device/invoked/{{device_id}}/function/{function_id}",
        payload=payload or {},
    )
    if not result["success"]:
        return _to_response(
            {"success": False, "error": result.get("error", "设备功能调用失败。")}
        )

    body = result.get("body")
    if not isinstance(body, dict):
        return _to_response({"success": False, "error": "JetLinks 返回格式错误。"})

    invoked = body.get("result", [])
    if body.get("status") != 200 or not invoked or not invoked[0].get("success", False):
        return _to_response(
            {
                "success": False,
                "error": body.get("message", "设备未成功执行指令。"),
            }
        )
    return _to_response({"success": True, "message": f"设备功能 {function_id} 调用成功。"})


invoke_device_function_desc = _function_desc(
    "invoke_device_function",
    "调用鱼缸设备功能。可用于喂食、换水、补水、排水和中断水处理流程。"
    "调用喂食功能时，可在 params 中传入 {\"times\": 份数}；其他功能无需 params。",
    {
        "type": "object",
        "properties": {
            "function_id": {
                "type": "string",
                "enum": [
                    "execute_feeding",
                    "start_water_change",
                    "start_top_off",
                    "start_drain",
                    "interrupt_water_proc",
                ],
                "description": "实际调用的 JetLinks 功能名称。",
            },
            "params": {
                "type": "object",
                "description": "功能参数；仅 execute_feeding 可传 {\"times\": 喂食份数}。",
            },
        },
        "required": ["function_id"],
    },
)


@register_function("invoke_device_function", invoke_device_function_desc, ToolType.IOT_CTL)
async def invoke_device_function(
    conn: "ConnectionHandler", function_id: str, params: dict | None = None
):
    return await _invoke_device_function(conn, function_id, params)
