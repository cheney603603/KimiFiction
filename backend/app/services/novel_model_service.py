"""小说级模型覆盖：读取 novels.model_* 列并注入上下文（三层回落：小说 > 用户BYOK > 全局）。"""
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.user_context import set_novel_config_snapshot
from app.models.novel import Novel


def build_novel_override(row: Novel) -> Optional[Dict[str, Any]]:
    """从小说行构建覆盖快照（仅含显式设置过的字段）。"""
    override: Dict[str, Any] = {}
    if row.model_provider:
        override["provider"] = row.model_provider
    if row.model_name:
        override["model"] = row.model_name
    if row.model_base_url:
        override["base_url"] = row.model_base_url
    return override or None


async def apply_novel_model_override(novel_id: int, db: AsyncSession) -> None:
    """读取小说级模型覆盖并写入当前上下文（协程级，生成链路自动回落）。"""
    row = (
        await db.execute(
            select(Novel).where(Novel.id == novel_id, Novel.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    set_novel_config_snapshot(build_novel_override(row) if row else None)
