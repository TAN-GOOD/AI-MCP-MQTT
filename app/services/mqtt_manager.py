import asyncio
import json
import time
import random
from typing import Dict, Optional, Any
from datetime import datetime
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from app.services.log_service import log_service


class MQTTClientWrapper:
    def __init__(self, project_id: int, broker: str, port: int = 1883,
                 username: str = None, password: str = None):
        self.project_id = project_id
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.client: Optional[mqtt.Client] = None
        self.message_cache: Dict[str, str] = {}
        self.subscribed_topics: set = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self):
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    async def connect(self) -> bool:
        try:
            self.client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id=f"xiaozhi_mcp_{self.project_id}_{int(time.time())}"
            )

            if self.username:
                self.client.username_pw_set(self.username, self.password)

            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_publish = self._on_publish

            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()

            await log_service.broadcast(
                self.project_id, "INFO",
                f"MQTT客户端初始化成功，连接到 {self.broker}:{self.port}"
            )
            return True
        except Exception as e:
            await log_service.broadcast(
                self.project_id, "ERROR",
                f"MQTT连接失败: {e}"
            )
            return False

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            loop = self._get_loop()
            asyncio.run_coroutine_threadsafe(
                log_service.broadcast(self.project_id, "INFO", f"MQTT连接成功 (code: {reason_code})"),
                loop
            )
            for topic in self.subscribed_topics:
                client.subscribe(topic, qos=1)
        else:
            loop = self._get_loop()
            asyncio.run_coroutine_threadsafe(
                log_service.broadcast(self.project_id, "ERROR", f"MQTT连接失败 (code: {reason_code})"),
                loop
            )

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        loop = self._get_loop()
        asyncio.run_coroutine_threadsafe(
            log_service.broadcast(self.project_id, "WARN", f"MQTT断开连接 (code: {reason_code})"),
            loop
        )

    def _on_message(self, client, userdata, message):
        try:
            payload = message.payload.decode('utf-8')
            self.message_cache[message.topic] = payload
            loop = self._get_loop()
            asyncio.run_coroutine_threadsafe(
                log_service.broadcast(
                    self.project_id, "MQTT",
                    f"← 收到 [{message.topic}]: {payload}"
                ),
                loop
            )
        except Exception as e:
            loop = self._get_loop()
            asyncio.run_coroutine_threadsafe(
                log_service.broadcast(self.project_id, "ERROR", f"处理MQTT消息错误: {e}"),
                loop
            )

    def _on_publish(self, client, userdata, mid, reason_code, properties):
        if reason_code == 0:
            loop = self._get_loop()
            asyncio.run_coroutine_threadsafe(
                log_service.broadcast(self.project_id, "DEBUG", f"→ 发布确认 (mid: {mid})"),
                loop
            )

    def subscribe(self, topic: str):
        self.subscribed_topics.add(topic)
        if self.client and self.client.is_connected():
            self.client.subscribe(topic, qos=1)

    def publish(self, topic: str, payload: str, qos: int = 1) -> bool:
        if not self.client or not self.client.is_connected():
            return False
        result = self.client.publish(topic, payload, qos=qos)
        return result.rc == 0

    def get_cached_message(self, topic: str) -> Optional[str]:
        return self.message_cache.get(topic)

    async def disconnect(self):
        if self.client:
            try:
                for topic in self.subscribed_topics:
                    self.client.unsubscribe(topic)
                self.client.loop_stop()
                self.client.disconnect()
                await log_service.broadcast(self.project_id, "INFO", "MQTT客户端已断开")
            except Exception as e:
                await log_service.broadcast(self.project_id, "ERROR", f"MQTT断开错误: {e}")


class MQTTManager:
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
        self.clients: Dict[int, MQTTClientWrapper] = {}

    async def get_or_create_client(
        self, project_id: int, broker: str, port: int = 1883,
        username: str = None, password: str = None
    ) -> MQTTClientWrapper:
        if project_id in self.clients:
            return self.clients[project_id]

        client = MQTTClientWrapper(project_id, broker, port, username, password)
        success = await client.connect()
        if success:
            self.clients[project_id] = client
        return client

    async def remove_client(self, project_id: int):
        if project_id in self.clients:
            await self.clients[project_id].disconnect()
            del self.clients[project_id]

    def get_client(self, project_id: int) -> Optional[MQTTClientWrapper]:
        return self.clients.get(project_id)


mqtt_manager = MQTTManager()
