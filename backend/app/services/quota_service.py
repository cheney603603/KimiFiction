"""额度墙服务（BYOK 产能订阅）：免费层 1 本书 + 每月固定章数，Pro 不限。

- novel_quota / monthly_chapter_quota 为 -1 表示不限（Pro）。
- 计费点：章节落库成功后 record_chapter_generated；小说创建成功后计数。
- 检查点：创建小说 / 生成章节前 assert_*，超限抛 QuotaExceeded（HTTP 402）。
"""
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

FREE_NOVEL_QUOTA = 1
FREE_MONTHLY_CHAPTER_QUOTA = 20
UNLIMITED = -1


class QuotaExceeded(Exception):
    """额度超限（前端应展示 402 与升级提示）。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _month_str(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now()).strftime("%Y-%m")


class QuotaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_user(self, user_id: int) -> Optional[User]:
        if not user_id:
            return None
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _quotas(user: User) -> Tuple[int, int]:
        """返回 (novel_quota, monthly_chapter_quota)。Pro 或未显式配置用默认。"""
        if getattr(user, "tier", "free") == "pro":
            return UNLIMITED, UNLIMITED
        return (
            getattr(user, "novel_quota", None) or FREE_NOVEL_QUOTA,
            getattr(user, "monthly_chapter_quota", None) or FREE_MONTHLY_CHAPTER_QUOTA,
        )

    async def _reset_if_needed(self, user: User) -> None:
        current = _month_str()
        if user.quota_month != current:
            user.quota_month = current
            user.monthly_chapters_used = 0

    async def assert_can_create_novel(self, user_id: Optional[int]) -> None:
        """免费层小说数超限时抛 QuotaExceeded。"""
        user = await self._load_user(user_id)
        if not user:
            return
        novel_quota, _ = self._quotas(user)
        if novel_quota == UNLIMITED:
            return
        from app.models.novel import Novel
        count = (
            await self.db.execute(
                select(func.count()).select_from(Novel).where(Novel.user_id == user_id)
            )
        ).scalar() or 0
        if count >= novel_quota:
            raise QuotaExceeded(f"免费层最多创建 {novel_quota} 本书（当前 {count} 本），升级 Pro 可无限创作")

    async def assert_can_generate_chapter(self, user_id: Optional[int]) -> None:
        """免费层本月章节数超限时抛 QuotaExceeded。"""
        user = await self._load_user(user_id)
        if not user:
            return
        await self._reset_if_needed(user)
        chapter_quota = self._quotas(user)[1]
        if chapter_quota == UNLIMITED:
            return
        used = user.monthly_chapters_used or 0
        if used >= chapter_quota:
            raise QuotaExceeded(f"本月已用完 {chapter_quota} 章额度（{used}/{chapter_quota}），升级 Pro 可无限生成")

    async def record_chapter_generated(self, user_id: Optional[int]) -> None:
        """章节落库成功后调用。Pro 不计数。"""
        user = await self._load_user(user_id)
        if not user:
            return
        await self._reset_if_needed(user)
        chapter_quota = self._quotas(user)[1]
        if chapter_quota != UNLIMITED:
            user.monthly_chapters_used = (user.monthly_chapters_used or 0) + 1
            await self.db.flush()

    async def get_status(self, user_id: Optional[int]) -> dict:
        """供前端展示：tier、上限与已用。"""
        user = await self._load_user(user_id)
        if not user:
            return {
                "tier": "free", "novel_quota": FREE_NOVEL_QUOTA, "novels_used": 0,
                "monthly_chapter_quota": FREE_MONTHLY_CHAPTER_QUOTA, "chapters_used": 0,
                "is_unlimited": False,
            }
        await self._reset_if_needed(user)
        novel_quota, chapter_quota = self._quotas(user)
        from app.models.novel import Novel
        novels_used = (
            await self.db.execute(
                select(func.count()).select_from(Novel).where(Novel.user_id == user_id)
            )
        ).scalar() or 0
        return {
            "tier": user.tier,
            "novel_quota": novel_quota,
            "novels_used": novels_used,
            "monthly_chapter_quota": chapter_quota,
            "chapters_used": user.monthly_chapters_used or 0,
            "is_unlimited": novel_quota == UNLIMITED and chapter_quota == UNLIMITED,
            "quota_month": user.quota_month,
        }
