"""
读者体验智能体
从读者视角评估章节可读性、情绪钩子和追读欲望
"""
from typing import Any, Dict

from app.agents.base import BaseAgent


class ReaderAgent(BaseAgent):
    """模拟目标读者反馈的Agent。"""

    SYSTEM_PROMPT = """你是一位真实且挑剔的网络小说读者。

你的职责是：
1. 从读者体验角度评价章节是否抓人
2. 指出让人困惑、出戏、节奏拖沓的地方
3. 评估情绪起伏、代入感、追读欲望
4. 给作者留下具体可执行的改进建议

输出必须是合法JSON。"""

    def __init__(self):
        super().__init__("Reader", self.SYSTEM_PROMPT)

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        chapter_number = context.get("chapter_number", 0)
        chapter_content = context.get("chapter_content", "")
        outline = context.get("outline", {})
        target_reader = context.get("target_reader", "大众网文读者")

        prompt = f"""请从“{target_reader}”的视角评价下面这一章。

章节号：第{chapter_number}章
章节细纲摘要：{outline.get("summary", "")}

章节正文：
{chapter_content[:6000]}

请输出JSON：
{{
  "reader_score": 0.0,
  "immersion_score": 0.0,
  "hook_score": 0.0,
  "confusing_points": ["困惑点1"],
  "boring_points": ["节奏问题1"],
  "most_engaging_moments": ["高光点1"],
  "reader_expectations": ["读者接下来想看什么"],
  "revision_suggestions": ["建议1"],
  "would_continue_reading": true
}}"""

        react_result = await self.run_react_loop(
            prompt,
            context=context,
            temperature=0.5,
            output_format="json",
        )
        response = react_result["final_text"] or react_result["raw_response"]
        result, parse_message = self._extract_json_with_message(response)
        if result is None:
            return {
                "success": False,
                "error": f"JSON解析失败: {parse_message}",
                "raw_response": response[:1000],
            }

        return {
            "success": True,
            "chapter_number": chapter_number,
            "reader_feedback": result,
            "_react_trace": react_result["trace"],
        }

    def _extract_json_with_message(self, response: str):
        from app.core.json_utils import extract_json_from_response
        return extract_json_from_response(response)
