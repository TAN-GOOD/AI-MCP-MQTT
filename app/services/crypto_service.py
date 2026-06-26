"""MQTT 凭据对称加密服务。

使用 Fernet 对称加密，密钥来源优先级：
1. settings.MQTT_CRED_KEY（显式配置的 Fernet key）
2. 从 settings.SECRET_KEY 派生（PBKDF2-HMAC-SHA256，固定 salt）

兼容策略：解密失败时返回原文（兼容历史明文数据），写入时一律加密。
"""
from __future__ import annotations

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_FERNET: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _FERNET
    if _FERNET is not None:
        return _FERNET

    if settings.MQTT_CRED_KEY:
        key = settings.MQTT_CRED_KEY.encode("utf-8")
    else:
        # 从 SECRET_KEY 派生 32 字节 key，再 base64 编码为 Fernet key
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            settings.SECRET_KEY.encode("utf-8"),
            b"xiaozhi-mcp-mqtt-cred-salt",
            iterations=100_000,
            dklen=32,
        )
        key = base64.urlsafe_b64encode(derived)
    _FERNET = Fernet(key)
    return _FERNET


def encrypt(plaintext: Optional[str]) -> Optional[str]:
    """加密明文，返回密文字符串；None/空串原样返回"""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: Optional[str]) -> Optional[str]:
    """解密；None/空串原样返回；解密失败（历史明文）返回原文"""
    if not ciphertext:
        return ciphertext
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        # 兼容历史明文数据
        return ciphertext
