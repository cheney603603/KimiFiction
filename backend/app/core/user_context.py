"""请求/任务级用户上下文（BYOK 配置解析用）。

HTTP 请求入口由中间件写入（user_id + 用户 LLM 配置快照）；
后台任务在入队时捕获快照，worker 处理前恢复，保证生成链路
即使在异步 worker 中也能解析到发起请求的那个用户的 Key。
"""
from contextvars import ContextVar, Token
from typing import Any, Dict, Optional

_current_user_id: ContextVar[Optional[int]] = ContextVar("current_user_id", default=None)
_user_config_snapshot: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "user_llm_config_snapshot", default=None
)
# 小说级模型覆盖（三层回落：小说 > 用户BYOK > 全局），由小说相关生成入口设置
_novel_config_snapshot: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "novel_llm_config_snapshot", default=None
)
# 用量归属（novel_id / chapter_number / phase），由工作流边界设置，供 LLM 用量日志记录
_usage_meta: ContextVar[Optional[Dict[str, Any]]] = ContextVar("llm_usage_meta", default=None)


def get_current_user_id() -> Optional[int]:
    return _current_user_id.get()


def get_user_config_snapshot() -> Optional[Dict[str, Any]]:
    """当前用户已解析的 LLM 配置快照（仅含用户显式设置过的字段）。"""
    return _user_config_snapshot.get()


def set_novel_config_snapshot(snapshot: Optional[Dict[str, Any]]) -> None:
    """设置小说级 LLM 配置覆盖快照（当前上下文，随协程传播）。"""
    _novel_config_snapshot.set(snapshot)


def get_novel_config_snapshot() -> Optional[Dict[str, Any]]:
    """读取小说级 LLM 配置覆盖快照。"""
    return _novel_config_snapshot.get()


def get_usage_meta() -> Optional[Dict[str, Any]]:
    return _usage_meta.get()


def set_usage_meta(meta: Optional[Dict[str, Any]]) -> None:
    _usage_meta.set(meta)


class UserContext:
    """上下文管理器：在任意作用域内设置/恢复用户上下文。"""

    def __init__(self, user_id: Optional[int], config_snapshot: Optional[Dict[str, Any]] = None):
        self._user_id = user_id
        self._config_snapshot = config_snapshot
        self._id_token: Optional[Token] = None
        self._cfg_token: Optional[Token] = None

    def __enter__(self) -> "UserContext":
        self._id_token = _current_user_id.set(self._user_id)
        self._cfg_token = _user_config_snapshot.set(self._config_snapshot)
        return self

    def __exit__(self, *exc) -> None:
        if self._cfg_token is not None:
            _user_config_snapshot.reset(self._cfg_token)
        if self._id_token is not None:
            _current_user_id.reset(self._id_token)


def capture() -> Dict[str, Any]:
    """捕获当前上下文，返回可存入任务/日志的 (user_id, config_snapshot)。"""
    return {
        "user_id": _current_user_id.get(),
        "llm_config_snapshot": _user_config_snapshot.get(),
    }


def apply(context: Dict[str, Any]) -> None:
    """直接把捕获的上下文写入当前任务（用于脱离 HTTP 的 Starlette BackgroundTask）。

    不做 reset：调用方应是一次性后台任务，任务结束后上下文即失效。
    """
    _current_user_id.set(context.get("user_id"))
    _user_config_snapshot.set(context.get("llm_config_snapshot"))


def restore(context: Dict[str, Any]) -> UserContext:
    """从 capture() 的结果恢复上下文，返回值作为上下文管理器使用。"""
    return UserContext(
        context.get("user_id"),
        context.get("llm_config_snapshot"),
    )
