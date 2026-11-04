"""API Key 加密存储工具（Fernet）。

密钥来自环境变量 APP_KEY_ENCRYPT_SECRET，未设置时禁止保存明文 Key。
任何明文字符串都会被派生为固定长度的 Fernet 密钥，因此 env 值无需是 base64。
"""
import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

_ENV_KEY = "APP_KEY_ENCRYPT_SECRET"


def _fernet() -> Fernet:
    secret = os.getenv(_ENV_KEY, "")
    if not secret:
        raise RuntimeError(
            f"未设置环境变量 {_ENV_KEY}，为避免 API Key 明文落库已禁止保存"
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    """加密明文字符串，返回可存库的密文。"""
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """解密存储的密文。密钥变更会导致解密失败并抛出异常。"""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("API Key 解密失败：APP_KEY_ENCRYPT_SECRET 可能已变更")
        raise
