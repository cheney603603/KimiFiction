"""
评审智能体
对生成内容进行质量评估
（已集成状态追踪）
"""
import json
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response
from app.services.llm_service_tracked import TrackedLLMService
from app.services.llm_service import LLMProvider
from app.core.llm_call_tracker import set_novel_context


class ReviewerAgent(BaseAgent):
    """
    评审智能体
    
    对章节、大纲、角色设计等进行质量评估
    """
    
    SYSTEM_PROMPT = """你是一位资深的小说编辑，擅长评估小说内容的质量。

你的任务是对给定的内容进行专业评估，包括：
1. 内容质量（情节、人物、文笔）
2. 结构合理性
3. 与设定的一致性
4. 改进建议

输出必须是合法的JSON格式。"""
    
    def __init__(self, novel_id: Optional[int] = None):
        super().__init__("Reviewer", self.SYSTEM_PROMPT)
        self.novel_id = novel_id
        if novel_id:
            self._llm = TrackedLLMService(
                provider=LLMProvider.DEEPSEEK,
                novel_id=novel_id,
                agent_name="reviewer",
                auto_track=True
            )
            set_novel_context(novel_id)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """评审内容"""
        novel_id = context.get("novel_id") or self.novel_id
        
        if novel_id:
            set_novel_context(novel_id)
            if not hasattr(self, '_llm') or not self._llm:
                self._llm = TrackedLLMService(
                    provider=LLMProvider.DEEPSEEK,
                    novel_id=novel_id,
                    agent_name="reviewer",
                    auto_track=True
                )
        
        content_type = context.get("content_type", "chapter")
        content = context.get("content", "")
        
        prompt = f"""请评审以下{content_type}：

{content[:5000]}

请输出JSON格式：
{{
  "overall_score": 85,
  "dimensions": {{
    "plot": {{"score": 85, "comment": "情节评价"}},
    "character": {{"score": 80, "comment": "人物评价"}},
    "writing": {{"score": 90, "comment": "文笔评价"}}
  }},
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["不足1", "不足2"],
  "suggestions": ["建议1", "建议2"]
}}"""
        
        try:
            response = await self._call_llm(prompt, output_format="json")
            result = extract_json_from_response(response)
            
            return {
                "success": True,
                "review": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
