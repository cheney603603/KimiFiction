"""工作流辅助函数：写作直达路径的兜底（缺细纲自动补全、语言质检重写）。"""
from typing import Any, Dict, List, Optional


async def language_rewrite(
    novel_id: int, content: str, failure_summary: str, chapter_number: int
) -> str:
    """语言质检未过 → 定向重写一轮（改稿人视角，只修语言不改情节）。失败/空返回空串。"""
    from app.services.llm_service import LLMProvider
    from app.services.llm_service_tracked import TrackedLLMService

    prompt = (
        "你是中文网文改稿人。下面这章语言质检未通过，硬禁令命中项如下：\n"
        f"{failure_summary}\n\n"
        "请在不改变情节、人物性格、对话内容的前提下，修复这些语言问题：\n"
        "- AI套词（不由得/霎时间/殊不知/良久/眼底闪过一丝波澜/喉结滚动等）换成具体动作或普通说法；\n"
        "- 删掉破折号，改逗号/句号或直接重写；\n"
        "- 拆掉“不是…而是…”“看似…实则…”这类翻案句，直接说事实；\n"
        "- 删模型路标词（值得注意的是/更重要的是/说白了等）。\n"
        "只输出修订后的完整章节正文，不要输出任何说明、标题或前后缀。\n\n"
        "原文如下：\n"
        + content
    )
    llm = TrackedLLMService(
        provider=LLMProvider.DEEPSEEK,
        novel_id=novel_id,
        agent_name="language_review",
        auto_track=True,
    )
    try:
        result = await llm.chat(
            [{"role": "user", "content": prompt}],
            description=f"语言质检重写 第{chapter_number}章",
        )
    except Exception:
        return ""
    return (result or "").strip()


async def auto_complete_chapter_outline(
    engine: Any, novel_id: int, chapter_number: int
) -> Optional[Dict[str, Any]]:
    """为缺失细纲的章节生成一份本章细纲；生成失败返回 None。

    仅兜底用：不要求先跑完整工作流，「继续创作」遇到缺细纲时补一份再写。
    """
    from app.agents.outline_generator import OutlineGeneratorAgent

    state = engine.state

    # 定位本章所属卷/剧情弧（大纲 volumes/arcs 结构存在则用，否则回落默认）
    arcs: List[Dict[str, Any]] = []
    if isinstance(state.outline, dict):
        for key in ("volumes", "arcs"):
            v = state.outline.get(key)
            if isinstance(v, list):
                arcs = [a for a in v if isinstance(a, dict)]
                break
    volume_number = 1
    arc_context = {"title": f"第{chapter_number}章", "description": ""}
    for idx, vol in enumerate(arcs, start=1):
        try:
            start = int(vol.get("start_chapter", 1) or 1)
            end = int(vol.get("end_chapter", 10 ** 6) or 10 ** 6)
        except (TypeError, ValueError):
            continue
        if start <= chapter_number <= end:
            volume_number = idx
            arc_context = {
                "title": str(vol.get("title") or ""),
                "description": str(vol.get("description") or ""),
            }
            break

    characters = [c for c in (state.characters or []) if isinstance(c, dict)]
    agent = OutlineGeneratorAgent(novel_id=novel_id)
    result = await agent.generate_chapter_outline(
        volume_number, chapter_number, arc_context, characters
    )
    if not isinstance(result, dict) or result.get("error") or not result.get("summary"):
        return None
    result["chapter_number"] = chapter_number
    result.setdefault("title", f"第{chapter_number}章")
    return result
