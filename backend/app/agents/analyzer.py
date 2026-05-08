"""
分析智能体
分析小说需求，提取关键信息
（已集成状态追踪）
"""
import json
from typing import Any, Dict, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response
from app.services.llm_service_tracked import TrackedLLMService
from app.services.llm_service import LLMProvider
from app.core.llm_call_tracker import set_novel_context


class AnalyzerAgent(BaseAgent):
    """
    需求分析智能体
    
    分析用户的创作需求，提取关键信息
    """
    
    SYSTEM_PROMPT = """你是一位专业的小说需求分析师。

你的任务是分析用户的创作需求，提取以下信息：
1. 小说类型和风格
2. 核心卖点和差异化
3. 目标读者群体
4. 内容尺度要求
5. 特殊需求或限制

输出必须是合法的JSON格式。"""
    
    def __init__(self, novel_id: Optional[int] = None):
        super().__init__("Analyzer", self.SYSTEM_PROMPT)
        self.novel_id = novel_id
        if novel_id:
            self._llm = TrackedLLMService(
                provider=LLMProvider.DEEPSEEK,
                novel_id=novel_id,
                agent_name="analyzer",
                auto_track=True
            )
            set_novel_context(novel_id)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析需求"""
        novel_id = context.get("novel_id") or self.novel_id
        
        if novel_id:
            set_novel_context(novel_id)
            if not hasattr(self, '_llm') or not self._llm:
                self._llm = TrackedLLMService(
                    provider=LLMProvider.DEEPSEEK,
                    novel_id=novel_id,
                    agent_name="analyzer",
                    auto_track=True
                )
        
        user_input = context.get("user_input", "")
        
        prompt = f"""请分析以下创作需求：

{user_input}

请输出JSON格式：
{{
  "genre": "小说类型",
  "style": "风格特点",
  "selling_points": ["卖点1", "卖点2"],
  "target_audience": "目标读者",
  "content_rating": "内容尺度",
  "special_requirements": ["特殊需求"],
  "estimated_volumes": 3,
  "estimated_chapters": 300
}}"""
        
        try:
            response = await self._call_llm(prompt, output_format="json")
            result = extract_json_from_response(response)
            
            return {
                "success": True,
                "analysis": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
