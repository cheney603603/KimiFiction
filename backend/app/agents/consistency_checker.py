"""
一致性检查智能体
检查内容的一致性
（已集成状态追踪）
"""
import json
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response
from app.services.llm_service_tracked import TrackedLLMService
from app.services.llm_service import LLMProvider
from app.core.llm_call_tracker import set_novel_context


class ConsistencyCheckerAgent(BaseAgent):
    """
    一致性检查智能体
    
    检查章节内容与设定的一致性
    """
    
    SYSTEM_PROMPT = """你是一位严谨的内容审核员，专门检查小说内容的一致性。

你的任务是检查：
1. 人物设定一致性（性格、能力、关系）
2. 世界观设定一致性（规则、地理、历史）
3. 剧情逻辑一致性（时间线、因果关系）
4. 伏笔回收情况

输出必须是合法的JSON格式。"""
    
    def __init__(self, novel_id: Optional[int] = None):
        super().__init__("ConsistencyChecker", self.SYSTEM_PROMPT)
        self.novel_id = novel_id
        if novel_id:
            self._llm = TrackedLLMService(
                provider=LLMProvider.DEEPSEEK,
                novel_id=novel_id,
                agent_name="consistency_checker",
                auto_track=True
            )
            set_novel_context(novel_id)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """检查一致性"""
        novel_id = context.get("novel_id") or self.novel_id
        
        if novel_id:
            set_novel_context(novel_id)
            if not hasattr(self, '_llm') or not self._llm:
                self._llm = TrackedLLMService(
                    provider=LLMProvider.DEEPSEEK,
                    novel_id=novel_id,
                    agent_name="consistency_checker",
                    auto_track=True
                )
        
        chapter_content = context.get("chapter_content", "")
        characters = context.get("characters", [])
        world_building = context.get("world_building", {})
        
        prompt = f"""请检查以下章节的一致性：

章节内容：
{chapter_content[:5000]}

角色设定：
{json.dumps(characters, ensure_ascii=False)}

世界观设定：
{json.dumps(world_building, ensure_ascii=False)}

请输出JSON格式：
{{
  "is_consistent": true,
  "issues": [
    {{"type": "character|world|plot", "description": "问题描述", "severity": "high|medium|low"}}
  ],
  "suggestions": ["修改建议"]
}}"""
        
        try:
            response = await self._call_llm(prompt, output_format="json")
            result = extract_json_from_response(response)
            
            return {
                "success": True,
                "consistency_check": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
