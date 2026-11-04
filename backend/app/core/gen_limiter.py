"""章节生成并发限制（按用户 tier，M3 轻量版）。

主生成路径是请求级 Starlette BackgroundTask，task_queue 的全局信号量管不到它们，
所以这里按 user_id 维护在途生成数：free 同刻只允许 1 个，Pro 用 PRO_CONCURRENCY。
"""
import asyncio
from collections import defaultdict
from typing import Optional

_inflight: "defaultdict[Optional[int], int]" = defaultdict(int)


async def wait_turn(user_id: Optional[int], limit: int) -> None:
    """等待直到该用户的在途生成数 < limit，然后占位。"""
    while _inflight[user_id] >= limit:
        await asyncio.sleep(1)
    _inflight[user_id] += 1


def done(user_id: Optional[int]) -> None:
    if _inflight[user_id] > 0:
        _inflight[user_id] -= 1
