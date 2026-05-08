"""
阶段需求评审智能体
评审各阶段产出是否满足需求
（已集成状态追踪）
"""
import json
from typing import Any, Dict, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response
from app.services.llm_service_tracked import TrackedLLMService
from app.services.llm_service import LLMProvider
from app.core.llm_call_tracker import set_novel_context


class PhaseRequirementReviewerAgent(BaseAgent):
    """
    阶段需求评审智能体
    
    检查各阶段产出是否符合需求规格
    """
    
    SYSTEM_PROMPT = """你是一位严格的需求评审员，负责检查产出是否符合需求规格。

你的任务是：
1. 对照需求检查产出
2. 识别遗漏和偏差
3. 评估完成度
4. 提出修改要求

输出必须是合法的JSON格式。"""
    
    def __init__(self, novel_id: Optional[int] = None):
        super().__init__("PhaseRequirementReviewer", self.SYSTEM_PROMPT)
        self.novel_id = novel_id
        if novel_id:
            self._llm = TrackedLLMService(
                provider=LLMProvider.DEEPSEEK,
                novel_id=novel_id,
                agent_name="phase_requirement_reviewer",
                auto_track=True
            )
            set_novel_context(novel_id)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """评审阶段产出"""
        novel_id = context.get("novel_id") or self.novel_id
        
        if novel_id:
            set_novel_context(novel_id)
            if not hasattr(self, '_llm') or not self._llm:
                self._llm = TrackedLLMService(
                    provider=LLMProvider.DEEPSEEK,
                    novel_id=novel_id,
                    agent_name="phase_requirement_reviewer",
                    auto_track=True
                )
        
        phase = context.get("phase", "")
        requirements = context.get("requirements", "")
        output = context.get("output", "")
        
        prompt = f"""请评审以下阶段产出：

阶段：{phase}

需求规格：
{requirements}

实际产出：
{output[:5000]}

请输出JSON格式：
{{
  "is_approved": true,
  "completion_rate": 85,
  "missing_items": ["遗漏项1"],
  "deviations": [{{"requirement": "需求", "actual": "实际", "severity": "high|medium|low"}}],
  "revision_requirements": ["修改要求"]
}}"""
        
        try:
            response = await self._call_llm(prompt, output_format="json")
            result = extract_json_from_response(response)
            
            return {
                "success": True,
                "review_result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
