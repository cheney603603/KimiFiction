"""额度墙 API（BYOK 产能订阅）。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import require_auth, require_superuser
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.quota_service import QuotaService

router = APIRouter()


@router.get("/status")
async def get_quota_status(
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """查询当前用户的额度（tier / 上限 / 已用）。"""
    return await QuotaService(db).get_status(current_user["id"])


class TierUpdateRequest(BaseModel):
    username: str
    tier: str = "pro"  # pro | free
    novel_quota: Optional[int] = None
    monthly_chapter_quota: Optional[int] = None


@router.post("/tier")
async def set_user_tier(
    payload: TierUpdateRequest,
    current_user: dict = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
):
    """管理员：置位用户 tier / 额度（真支付上线前的临时通道）。"""
    if payload.tier not in ("pro", "free"):
        raise HTTPException(status_code=400, detail="tier 仅支持 pro/free")
    from sqlalchemy import select
    from app.models.user import User
    user = (await db.execute(
        select(User).where(User.username == payload.username)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.tier = payload.tier
    if payload.novel_quota is not None:
        user.novel_quota = payload.novel_quota
    if payload.monthly_chapter_quota is not None:
        user.monthly_chapter_quota = payload.monthly_chapter_quota
    await db.flush()
    return {"success": True, "username": payload.username, "tier": payload.tier}
