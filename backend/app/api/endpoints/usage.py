"""LLM 用量统计 API（开书/每章 token、阶段重试次数）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_auth
from app.core.database import get_db
from app.services.llm_usage_service import LLMUsageService

router = APIRouter()


@router.get("/novel/{novel_id}")
async def get_novel_usage(
    novel_id: int,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """单本书用量：总 token、按阶段/章节分布、重试与失败统计。"""
    return await LLMUsageService(db).novel_summary(novel_id)


@router.get("/summary")
async def get_usage_summary(
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """全局用量汇总（最近 5000 条）。"""
    return await LLMUsageService(db).global_summary()
