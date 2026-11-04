"""用户级 LLM 配置读写服务（BYOK）。"""
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secret_box import decrypt_secret, encrypt_secret
from app.models.user_llm_config import UserLLMConfig


class LLMUserConfigService:
    """读写单个用户的 BYOK 配置，api_key 一律密文落库。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: int) -> Optional[UserLLMConfig]:
        result = await self.db.execute(
            select(UserLLMConfig).where(UserLLMConfig.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_snapshot(self, user_id: int) -> Dict[str, Any]:
        """返回用户配置的明文快照（供 UserContext 使用），仅含显式设置过的字段。"""
        row = await self.get_by_user_id(user_id)
        if not row:
            return {}
        snapshot: Dict[str, Any] = {}
        if row.provider:
            snapshot["provider"] = row.provider
        if row.api_key_enc:
            try:
                snapshot["api_key"] = decrypt_secret(row.api_key_enc)
            except Exception:
                return {}
        if row.base_url:
            snapshot["base_url"] = row.base_url
        if row.model:
            snapshot["model"] = row.model
        return snapshot

    async def upsert(self, user_id: int, config: Dict[str, Any]) -> None:
        """保存用户配置（api_key 明文入参，方法内加密落库）。"""
        row = await self.get_by_user_id(user_id)
        if row is None:
            row = UserLLMConfig(user_id=user_id)
            self.db.add(row)
        if config.get("provider"):
            row.provider = config["provider"]
        if config.get("api_key"):
            row.api_key_enc = encrypt_secret(config["api_key"])
        if "base_url" in config:
            row.base_url = config.get("base_url") or None
        if "model" in config:
            row.model = config.get("model") or None
        await self.db.flush()

    async def delete(self, user_id: int) -> bool:
        """删除用户配置（移除其 Key）。"""
        row = await self.get_by_user_id(user_id)
        if not row:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True
