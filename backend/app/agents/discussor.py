"""
讨论智能体
多Agent讨论协调
（已集成状态追踪）
"""
import json
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response
from app.services.llm_service_tracked import TrackedLLMService
from app.services.llm_service import LLMProvider
from app.core.llm_call_tracker import set_novel_context


class DiscussorAgent(BaseAgent):
    """
    讨论协调智能体
    
    协调多个Agent进行讨论，达成共识
    """
    
    SYSTEM_PROMPT = """你是一位讨论主持人，擅长协调多方意见达成共识。

你的任务是：
1. 汇总各方观点
2. 识别分歧点
3. 提出协调方案
4. 促成最终决策

输出必须是合法的JSON格式。"""
    
    def __init__(self, novel_id: Optional[int] = None):
        super().__init__("Discussor", self.SYSTEM_PROMPT)
        self.novel_id = novel_id
        if novel_id:
            self._llm = TrackedLLMService(
                provider=LLMProvider.DEEPSEEK,
                novel_id=novel_id,
                agent_name="discussor",
                auto_track=True
            )
            set_novel_context(novel_id)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """协调讨论"""
        novel_id = context.get("novel_id") or self.novel_id
        
        if novel_id:
            set_novel_context(novel_id)
            if not hasattr(self, '_llm') or not self._llm:
                self._llm = TrackedLLMService(
                    provider=LLMProvider.DEEPSEEK,
                    novel_id=novel_id,
                    agent_name="discussor",
                    auto_track=True
                )
        
        topic = context.get("topic", "")
        opinions = context.get("opinions", [])
        
        prompt = f"""请协调以下讨论：

讨论主题：{topic}

各方观点：
{json.dumps(opinions, ensure_ascii=False, indent=2)}

请输出JSON格式：
{{
  "consensus_reached": true,
  "summary": "讨论总结",
  "agreed_points": ["共识点1", "共识点2"],
  "disputed_points": ["分歧点1"],
  "final_decision": "最终决策",
  "action_items": ["行动项1"]
}}"""
        
        try:
            response = await self._call_llm(prompt, output_format="json")
            result = extract_json_from_response(response)
            
            return {
                "success": True,
                "discussion_result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
