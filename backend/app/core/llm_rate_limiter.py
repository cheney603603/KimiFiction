"""全局 LLM 速率限制（RPM，滑动窗口）。

防止并发批量生成把网关打爆（联影网关 503 资源池已满）。
RPM=0 表示不限速。默认 40（LLM_RPM_LIMIT 环境变量可调）。
"""
import asyncio
import time

from loguru import logger

from app.core.config import settings


class LLMRateLimiter:
    def __init__(self, rpm: int | None = None):
        self.rpm = rpm if rpm is not None else settings.LLM_RPM_LIMIT
        self._window_start = 0.0
        self._count = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        if self.rpm <= 0:
            return
        while True:
            async with self._lock:
                now = time.monotonic()
                if now - self._window_start >= 60:
                    self._window_start = now
                    self._count = 0
                if self._count < self.rpm:
                    self._count += 1
                    return
                wait = 60 - (now - self._window_start)
            await asyncio.sleep(min(max(wait, 0.1), 1.0))

    @property
    def current(self) -> int:
        return self._count


# 全局限速器实例
llm_rate_limiter = LLMRateLimiter()
