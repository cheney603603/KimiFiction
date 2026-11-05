"""LLM 用量日志服务：记录与聚合（开书/每章 token、各阶段重试次数）。"""
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage_log import LLMUsageLog


class LLMUsageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(self, **kwargs) -> None:
        """写入一条用量记录（尽力而为，失败不抛）。"""
        try:
            self.db.add(LLMUsageLog(**kwargs))
            await self.db.flush()
        except Exception:
            await self.db.rollback()

    async def novel_summary(self, novel_id: int) -> Dict[str, Any]:
        """单本书用量：总量 + 按阶段 + 按章节 + 重试/失败统计。"""
        rows = (await self.db.execute(
            select(LLMUsageLog).where(LLMUsageLog.novel_id == novel_id)
        )).scalars().all()

        total_in = sum(r.tokens_in for r in rows)
        total_out = sum(r.tokens_out for r in rows)
        total_calls = len(rows)
        failed = [r for r in rows if r.status == "error"]
        retry_calls = [r for r in rows if r.retry_count > 0]

        phases: Dict[str, Dict[str, int]] = {}
        chapters: Dict[str, Dict[str, int]] = {}
        for r in rows:
            key_ph = r.phase or "未知"
            p = phases.setdefault(key_ph, {"calls": 0, "tokens_in": 0, "tokens_out": 0,
                                            "retries": 0, "errors": 0})
            p["calls"] += 1
            p["tokens_in"] += r.tokens_in
            p["tokens_out"] += r.tokens_out
            p["retries"] += r.retry_count
            p["errors"] += 1 if r.status == "error" else 0
            if r.chapter_number is not None:
                key_ch = f"第{r.chapter_number}章"
                c = chapters.setdefault(key_ch, {"calls": 0, "tokens_in": 0, "tokens_out": 0,
                                                  "retries": 0, "errors": 0})
                c["calls"] += 1
                c["tokens_in"] += r.tokens_in
                c["tokens_out"] += r.tokens_out
                c["retries"] += r.retry_count
                c["errors"] += 1 if r.status == "error" else 0

        return {
            "novel_id": novel_id,
            "total_calls": total_calls,
            "total_tokens_in": total_in,
            "total_tokens_out": total_out,
            "total_tokens": total_in + total_out,
            "avg_tokens_per_call": round((total_in + total_out) / total_calls, 1) if total_calls else 0,
            "error_calls": len(failed),
            "retried_calls": len(retry_calls),
            "total_retries": sum(r.retry_count for r in rows),
            "by_phase": phases,
            "by_chapter": chapters,
        }

    async def global_summary(self, limit: int = 5000) -> Dict[str, Any]:
        """全局用量汇总（最近 limit 条）。"""
        rows = (await self.db.execute(
            select(LLMUsageLog).order_by(LLMUsageLog.created_at.desc()).limit(limit)
        )).scalars().all()
        total_in = sum(r.tokens_in for r in rows)
        total_out = sum(r.tokens_out for r in rows)
        return {
            "calls": len(rows),
            "total_tokens_in": total_in,
            "total_tokens_out": total_out,
            "total_tokens": total_in + total_out,
            "error_calls": sum(1 for r in rows if r.status == "error"),
            "total_retries": sum(r.retry_count for r in rows),
        }
