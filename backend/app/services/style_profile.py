"""
文风解析：从小说资产读取写作风格（P0-10 去硬编码）
==================================================

优先级：显式 style_prompt > 小说 style_profile > 类型分析关键词 > 默认。

P1 将在此扩展「风格锚点」（style_profile few-shot 样本），见 §5.1。
"""
import json
from typing import Any, Dict, Optional

DEFAULT_WRITING_STYLE = "叙事流畅，情节紧凑"


def resolve_writing_style(
    state: Optional[Dict[str, Any]] = None,
    novel_style_prompt: Optional[str] = None,
    user_override: Optional[str] = None,
) -> str:
    """解析写作风格。

    Args:
        state: 工作流状态（含 style_prompt / genre_analysis / demand_analysis）
        novel_style_prompt: 小说资产显式风格提示（最高优先，除用户覆盖外）
        user_override: 接口/前端传入的临时覆盖（最高优先）
    """
    if user_override and str(user_override).strip():
        return str(user_override).strip()

    if novel_style_prompt and str(novel_style_prompt).strip():
        return str(novel_style_prompt).strip()

    if state:
        sp = state.get("style_prompt")
        if sp and str(sp).strip():
            return str(sp).strip()

        for key in ("genre_analysis", "demand_analysis"):
            ga = state.get(key)
            if isinstance(ga, str):
                try:
                    ga = json.loads(ga)
                except Exception:
                    ga = None
            if isinstance(ga, dict):
                kws = ga.get("style_keywords") or ga.get("style") or ga.get("suggested_style")
                if isinstance(kws, list) and kws:
                    return "、".join(str(k) for k in kws)
                genre = ga.get("suggested_genre") or ga.get("genre")
                if genre:
                    return f"{genre}文风"

    return DEFAULT_WRITING_STYLE
