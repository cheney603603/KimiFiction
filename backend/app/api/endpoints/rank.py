"""番茄榜单 API：品类列表 + 榜单查询（快照缓存 / 实时刷新）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_auth
from app.core.database import get_db
from app.services.fanqie_rank_service import FanqieRankService

router = APIRouter()


@router.get("/genres")
async def list_genres(
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """番茄 37 个品类（男频/女频）。"""
    return {"items": await FanqieRankService(db).categories()}


@router.get("/fanqie")
async def get_fanqie_rank(
    gender: str = Query("male", description="male/female"),
    genre_id: str = Query(..., description="品类 ID（来自 /rank/genres）"),
    genre: str = Query("", description="品类名（用于快照标记，可省）"),
    rank_type: str = Query("read", description="read(阅读榜)/new(新书榜)"),
    top: int = Query(20, ge=1, le=50),
    refresh: int = Query(0, description="1=强制实时刷新"),
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """番茄榜单：优先当日快照，refresh=1 实时抓取并更新快照。"""
    svc = FanqieRankService(db)
    items = await svc.get_or_fetch(
        gender=gender, genre_id=genre_id, genre=genre or "",
        rank_type=rank_type, top=top, refresh=bool(refresh),
    )
    await db.commit()
    return {"gender": gender, "genre_id": genre_id, "rank_type": rank_type,
            "count": len(items), "items": items}
