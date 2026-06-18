import asyncio
import json
import ssl
import time
import traceback
import random
from typing import Dict, Optional, Any, List
import websockets
import httpx

from app.services.log_service import log_service
from app.services.mqtt_manager import mqtt_manager
from app.services.json_path import parse_json_path, try_parse_json


class MCPConnection:
    def __init__(self, project_id: int, config: dict):
        self.project_id = project_id
        self.config = config
        self.ws = None
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.protocol_version = "2024-11-05"

    def _build_tools(self, tools_config: list) -> list:
        mcp_tools = []
        for tool in tools_config:
            tool_type = tool.get("tool_type", "")
            name = tool.get("name", "")
            description = tool.get("description", "")
            config = tool.get("config", {})
            commands = config.get("commands", [])

            if tool_type == "mqtt_publish":
                cmd_values = [c["value"] for c in commands]
                cmd_desc = ", ".join(f'{c["value"]}={c["label"]}' for c in commands)
                payload_template = config.get("payload_template", "")

                mcp_config = {
                    "topic": config.get("topic", ""),
                }
                if payload_template:
                    mcp_config["payloadTemplate"] = payload_template

                mcp_tools.append({
                    "name": name,
                    "description": description,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "enum": cmd_values,
                                "description": cmd_desc,
                            }
                        },
                        "required": ["command"],
                        "title": f"{name}Arguments",
                        "mqttConfig": mcp_config
                    }
                })

            elif tool_type == "mqtt_subscribe":
                json_path = config.get("json_path", "")

                sub_config = {
                    "topic": config.get("topic", ""),
                }
                if json_path:
                    sub_config["jsonPath"] = json_path

                mcp_tools.append({
                    "name": name,
                    "description": description,
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "title": f"{name}Arguments",
                        "mqttSubscriberConfig": sub_config
                    }
                })

            elif tool_type == "http_request":
                cmd_values = [c["value"] for c in commands]
                cmd_desc = ", ".join(f'{c["value"]}={c["label"]}' for c in commands)

                mcp_tools.append({
                    "name": name,
                    "description": description,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "enum": cmd_values,
                                "description": cmd_desc,
                            }
                        },
                        "required": ["command"],
                        "title": f"{name}Arguments",
                        "apiConfig": {
                            "url": config.get("url", ""),
                            "method": config.get("method", "GET"),
                        }
                    }
                })

        return mcp_tools

    async def _handle_message(self, message: str, tools_config: list) -> str:
        try:
            msg = json.loads(message)
            method = msg.get("method")
            msg_id = msg.get("id")

            if method not in ["ping", "heartbeat"]:
                await log_service.broadcast(
                    self.project_id, "DEBUG",
                    f"MCP收到请求: method={method}, id={msg_id}"
                )

            if method == "initialize":
                return json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "protocolVersion": self.protocol_version,
                        "capabilities": {
                            "experimental": {},
                            "prompts": {"listChanged": False},
                            "resources": {"subscribe": False, "listChanged": False},
                            "tools": {"listChanged": False}
                        },
                        "serverInfo": {
                            "name": f"XiaoZhiMCP_Project_{self.project_id}",
                            "version": "1.0.0"
                        }
                    }
                })

            elif method == "notifications/initialized":
                return ""

            elif method == "tools/list":
                tools = self._build_tools(tools_config)
                await log_service.broadcast(
                    self.project_id, "INFO",
                    f"返回工具列表: {[t['name'] for t in tools]}"
                )
                return json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {"tools": tools}
                })

            elif method == "tools/call":
                params = msg.get("params", {})
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})

                await log_service.broadcast(
                    self.project_id, "INFO",
                    f"调用工具: {tool_name}, 参数: {json.dumps(arguments, ensure_ascii=False)}"
                )

                tool_config = None
                for t in tools_config:
                    if t["name"] == tool_name:
                        tool_config = t
                        break

                if not tool_config:
                    return json.dumps({
                        "jsonrpc": "2.0", "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": f"工具 {tool_name} 不存在"}],
                            "isError": True
                        }
                    })

                result = await self._execute_tool(tool_config, arguments)
                return json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": result
                })

            elif method == "ping":
                return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {}})

            elif method == "heartbeat":
                return json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {"content": [{"type": "text", "text": "ok"}], "isError": False}
                })

            else:
                return json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": f"未知方法: {method}"}],
                        "isError": True
                    }
                })

        except json.JSONDecodeError as e:
            return json.dumps({
                "jsonrpc": "2.0", "id": None,
                "result": {
                    "content": [{"type": "text", "text": f"JSON解析错误: {e}"}],
                    "isError": True
                }
            })
        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0", "id": msg.get("id") if 'msg' in locals() else None,
                "result": {
                    "content": [{"type": "text", "text": f"错误: {e}"}],
                    "isError": True
                }
            })

    async def _execute_tool(self, tool_config: dict, arguments: dict) -> dict:
        tool_type = tool_config.get("tool_type", "")
        config = tool_config.get("config", {})
        tool_name = tool_config.get("name", "")

        try:
            if tool_type == "mqtt_publish":
                return await self._execute_mqtt_publish(config, arguments, tool_name)
            elif tool_type == "mqtt_subscribe":
                return await self._execute_mqtt_subscribe(config, tool_name)
            elif tool_type == "http_request":
                return await self._execute_http_request(config, arguments, tool_name)
            else:
                return {
                    "content": [{"type": "text", "text": f"不支持的工具类型: {tool_type}"}],
                    "isError": True
                }
        except Exception as e:
            await log_service.broadcast(
                self.project_id, "ERROR",
                f"工具 {tool_name} 执行失败: {e}"
            )
            return {
                "content": [{"type": "text", "text": f"工具执行失败: {e}"}],
                "isError": True
            }

    async def _execute_mqtt_publish(self, config: dict, arguments: dict, tool_name: str) -> dict:
        mqtt_client = mqtt_manager.get_client(self.project_id)
        if not mqtt_client:
            return {
                "content": [{"type": "text", "text": "MQTT客户端未连接"}],
                "isError": True
            }

        topic = config.get("topic", "")
        command = arguments.get("command", "")
        payload_template = config.get("payload_template", "")

        if payload_template:
            payload = payload_template.replace("{{command}}", command)
        else:
            payload = command

        await log_service.broadcast(
            self.project_id, "INFO",
            f"发送MQTT消息: 主题={topic}, 命令={payload}"
        )

        success = mqtt_client.publish(topic, payload)
        if success:
            return {
                "content": [{"type": "text", "text": f"已发送命令 {payload} 到 {topic}"}],
                "isError": False
            }
        else:
            return {
                "content": [{"type": "text", "text": "MQTT消息发送失败"}],
                "isError": True
            }

    async def _execute_mqtt_subscribe(self, config: dict, tool_name: str) -> dict:
        mqtt_client = mqtt_manager.get_client(self.project_id)
        if not mqtt_client:
            return {
                "content": [{"type": "text", "text": "MQTT客户端未连接"}],
                "isError": True
            }

        topic = config.get("topic", "")
        json_path = config.get("json_path", "")
        message = mqtt_client.get_cached_message(topic)

        if message:
            result_text = message

            if json_path:
                parsed = try_parse_json(message)
                if parsed is not None:
                    extracted = parse_json_path(parsed, json_path)
                    if extracted is not None:
                        if isinstance(extracted, (dict, list)):
                            result_text = json.dumps(extracted, ensure_ascii=False)
                        else:
                            result_text = str(extracted)
                        await log_service.broadcast(
                            self.project_id, "INFO",
                            f"JsonPath解析: {json_path} → {result_text}"
                        )
                    else:
                        result_text = f"JsonPath {json_path} 未匹配到数据，原始消息: {message}"
                else:
                    await log_service.broadcast(
                        self.project_id, "WARN",
                        f"消息不是有效JSON，返回原始数据"
                    )

            return {
                "content": [{"type": "text", "text": result_text}],
                "isError": False
            }
        else:
            return {
                "content": [{"type": "text", "text": f"尚未收到主题 {topic} 的消息"}],
                "isError": False
            }

    async def _execute_http_request(self, config: dict, arguments: dict, tool_name: str) -> dict:
        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        command = arguments.get("command", "")

        await log_service.broadcast(
            self.project_id, "INFO",
            f"调用HTTP接口: {method} {url}, 命令={command}"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            if method == "GET":
                response = await client.get(url, params={"command": command})
            elif method == "POST":
                response = await client.post(url, json={"command": command})
            elif method == "PUT":
                response = await client.put(url, json={"command": command})
            elif method == "DELETE":
                response = await client.delete(url, params={"command": command})
            else:
                return {
                    "content": [{"type": "text", "text": f"不支持的HTTP方法: {method}"}],
                    "isError": True
                }

        try:
            result = response.json()
            result_text = json.dumps(result, ensure_ascii=False)
        except Exception:
            result_text = response.text

        await log_service.broadcast(
            self.project_id, "INFO",
            f"HTTP响应 ({response.status_code}): {result_text[:200]}"
        )

        return {
            "content": [{"type": "text", "text": result_text}],
            "isError": response.status_code >= 400
        }

    async def start(self, tools_config: list):
        if self.running:
            return

        self.running = True
        self.task = asyncio.create_task(self._run(tools_config))

    async def _run(self, tools_config: list):
        mcp_endpoint = self.config.get("mcp_endpoint", "")
        if not mcp_endpoint:
            await log_service.broadcast(self.project_id, "ERROR", "MCP接入点地址为空")
            self.running = False
            return

        await log_service.broadcast(
            self.project_id, "INFO",
            f"正在连接MCP接入点: {mcp_endpoint}"
        )

        reconnect_attempts = 0
        max_reconnect = 10
        base_delay = 5

        while self.running:
            try:
                ssl_context = None
                if mcp_endpoint.startswith('wss://'):
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

                async with websockets.connect(
                    mcp_endpoint,
                    ssl=ssl_context,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                    open_timeout=20
                ) as ws:
                    self.ws = ws
                    reconnect_attempts = 0
                    await log_service.broadcast(
                        self.project_id, "INFO",
                        f"MCP WebSocket连接成功"
                    )
                    await log_service.broadcast_status(self.project_id, True)

                    async for message in ws:
                        if not self.running:
                            break
                        for line in str(message).strip().split('\n'):
                            if line.strip():
                                response = await self._handle_message(line.strip(), tools_config)
                                if response:
                                    await ws.send(response)

            except websockets.exceptions.ConnectionClosed:
                await log_service.broadcast(self.project_id, "WARN", "MCP连接被关闭")
            except asyncio.TimeoutError:
                await log_service.broadcast(self.project_id, "WARN", "MCP连接超时")
            except Exception as e:
                await log_service.broadcast(
                    self.project_id, "ERROR",
                    f"MCP连接异常: {e}"
                )

            if not self.running:
                break

            reconnect_attempts += 1
            if reconnect_attempts >= max_reconnect:
                await log_service.broadcast(
                    self.project_id, "ERROR",
                    f"达到最大重连次数 ({max_reconnect})，停止重连"
                )
                break

            delay = min(base_delay * (2 ** (reconnect_attempts - 1)), 60)
            jitter = delay * 0.3 * (2 * random.random() - 1)
            delay = max(1, delay + jitter)

            await log_service.broadcast(
                self.project_id, "INFO",
                f"{delay:.1f}秒后尝试重连... 第{reconnect_attempts}次"
            )
            await asyncio.sleep(delay)

        self.running = False
        await log_service.broadcast_status(self.project_id, False)

    async def stop(self):
        self.running = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await log_service.broadcast_status(self.project_id, False)

    def update_tools(self, tools_config: list):
        self.config["tools_config"] = tools_config


class MCPManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.connections: Dict[int, MCPConnection] = {}

    async def start_project(self, project_id: int, project_config: dict, tools_config: list):
        if project_id in self.connections:
            await self.stop_project(project_id)

        conn = MCPConnection(project_id, project_config)
        conn.config["tools_config"] = tools_config
        self.connections[project_id] = conn
        await conn.start(tools_config)

    async def stop_project(self, project_id: int):
        if project_id in self.connections:
            await self.connections[project_id].stop()
            del self.connections[project_id]

    def get_connection(self, project_id: int) -> Optional[MCPConnection]:
        return self.connections.get(project_id)

    def is_running(self, project_id: int) -> bool:
        conn = self.connections.get(project_id)
        return conn.running if conn else False

    async def restart_project(self, project_id: int, project_config: dict, tools_config: list):
        await self.stop_project(project_id)
        await self.start_project(project_id, project_config, tools_config)


mcp_manager = MCPManager()
