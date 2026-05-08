"""
剧情设计智能体
设计剧情弧和关键情节
（已集成状态追踪）
"""
import json
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response
from app.services.llm_service_tracked import TrackedLLMService
from app.services.llm_service import LLMProvider
from app.core.llm_call_tracker import set_novel_context


class PlotDesignerAgent(BaseAgent):
    """
    剧情设计智能体
    
    设计剧情弧、关键情节和转折点
    """
    
    SYSTEM_PROMPT = """你是一位资深的剧情设计师，擅长创造引人入胜的故事情节。

你的任务是：
1. 设计主要剧情弧
2. 规划关键情节节点
3. 设置转折点和悬念
4. 安排伏笔和回收
5. 确保节奏张弛有度

输出必须是合法的JSON格式。"""
    
    def __init__(self, novel_id: Optional[int] = None):
        super().__init__("PlotDesigner", self.SYSTEM_PROMPT)
        self.novel_id = novel_id
        if novel_id:
            self._llm = TrackedLLMService(
                provider=LLMProvider.DEEPSEEK,
                novel_id=novel_id,
                agent_name="plot_designer",
                auto_track=True
            )
            set_novel_context(novel_id)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """设计剧情"""
        novel_id = context.get("novel_id") or self.novel_id
        
        if novel_id:
            set_novel_context(novel_id)
            if not hasattr(self, '_llm') or not self._llm:
                self._llm = TrackedLLMService(
                    provider=LLMProvider.DEEPSEEK,
                    novel_id=novel_id,
                    agent_name="plot_designer",
                    auto_track=True
                )
        
        genre = context.get("genre", "玄幻")
        characters = context.get("characters", [])
        world_building = context.get("world_building", {})
        
        prompt = f"""请为以下小说设计剧情：

类型：{genre}
角色：{json.dumps(characters, ensure_ascii=False)}
世界观：{json.dumps(world_building, ensure_ascii=False)}

请输出JSON格式：
{{
  "plot_arcs": [
    {{
      "name": "剧情弧名称",
      "start_chapter": 1,
      "end_chapter": 50,
      "summary": "剧情概要",
      "key_events": ["关键事件1", "关键事件2"],
      "climax": "高潮设计",
      "resolution": "解决方式"
    }}
  ],
  "turning_points": [
    {{"chapter": 25, "description": "转折点描述", "impact": "影响"}}
  ],
  "foreshadowing": [
    {{"hint": "伏笔", "resolve_chapter": 80, "description": "回收方式"}}
  ]
}}"""
        
        try:
            response = await self._call_llm(prompt, output_format="json")
            result = extract_json_from_response(response)
            
            return {
                "success": True,
                "plot_design": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
