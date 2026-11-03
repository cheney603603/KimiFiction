"""
设定预检（P2）
============

在阶段执行/章节写作前，对世界观、角色、大纲做完整性预检，输出问题清单。
非阻塞：仅告警，不阻断流程。
"""
from typing import Any, Dict, List, Optional


def precheck_world_setting(world_setting: Dict[str, Any]) -> List[str]:
    """世界观设定完整性检查。"""
    issues: List[str] = []
    ws = world_setting or {}
    if not ws:
        issues.append("世界观设定为空")
        return issues
    for key in ("power_systems", "geography", "regions", "major_factions"):
        if not ws.get(key):
            issues.append(f"世界观缺少字段: {key}")
    return issues


def precheck_characters(characters: List[Dict]) -> List[str]:
    """角色卡完整性检查。"""
    issues: List[str] = []
    for i, c in enumerate(characters or []):
        name = c.get("name", "")
        if not name:
            issues.append(f"第{i + 1}个角色缺少 name")
            continue
        if not c.get("role_type"):
            issues.append(f"角色 {name} 缺少 role_type")
        profile = c.get("profile") or {}
        if not profile.get("personality"):
            issues.append(f"角色 {name} 缺少性格设定")
        if not profile.get("dialogue_style") and not c.get("dialogue_style"):
            issues.append(f"角色 {name} 缺少说话风格")
    return issues


def precheck_outline(outline: Dict[str, Any]) -> List[str]:
    """章节细纲完整性检查。"""
    issues: List[str] = []
    if not outline:
        return ["章节细纲为空"]
    if not outline.get("summary"):
        issues.append("细纲缺少 summary")
    if not outline.get("key_points") and not outline.get("key_events"):
        issues.append("细纲缺少 key_points/key_events")
    return issues


def precheck_all(state: Dict[str, Any]) -> Dict[str, List[str]]:
    """汇总预检。"""
    return {
        "world_setting": precheck_world_setting(state.get("world_setting") or {}),
        "characters": precheck_characters(state.get("characters") or []),
        "outline": precheck_outline(state.get("outline") or {}),
    }
