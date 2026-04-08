"""
Agent 专用日志系统
分别记录 workflow 日志与 dialogue 日志
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path("logs/agents")
WORKFLOW_DIR = BASE_DIR / "workflow"
DIALOGUE_DIR = BASE_DIR / "dialogue"


def _ensure_dirs() -> None:
    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
    DIALOGUE_DIR.mkdir(parents=True, exist_ok=True)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_dirs()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=_json_default) + "\n")


def build_agent_context(context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    context = context or {}
    return {
        "workflow_id": context.get("workflow_id"),
        "novel_id": context.get("novel_id"),
        "chapter_number": context.get("chapter_number"),
        "phase": context.get("phase"),
        "loop_round": context.get("loop_round"),
    }


def log_agent_workflow(
    agent_name: str,
    event: str,
    *,
    context: Optional[Dict[str, Any]] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "event": event,
        "context": build_agent_context(context),
        "details": details or {},
    }
    _append_jsonl(WORKFLOW_DIR / f"{agent_name}.jsonl", payload)


def log_agent_dialogue(
    agent_name: str,
    *,
    prompt: str,
    response: str,
    context: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "context": build_agent_context(context),
        "prompt": prompt,
        "response": response,
        "metadata": metadata or {},
    }
    _append_jsonl(DIALOGUE_DIR / f"{agent_name}.jsonl", payload)


def log_agent_trace(
    agent_name: str,
    trace: List[Dict[str, Any]],
    *,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "context": build_agent_context(context),
        "trace": trace,
    }
    _append_jsonl(WORKFLOW_DIR / f"{agent_name}_trace.jsonl", payload)
