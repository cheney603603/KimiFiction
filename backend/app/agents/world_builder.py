"""
世界观构建智能体
根据小说类型和需求，构建完整的世界观设定
（已集成状态追踪）
"""
import json
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response
from app.services.llm_service_tracked import TrackedLLMService
from app.services.llm_service import LLMProvider
from app.core.llm_call_tracker import set_novel_context


class WorldBuilderAgent(BaseAgent):
    """
    世界观构建智能体
    
    负责：
    1. 分析小说类型，确定世界观框架
    2. 构建力量体系/社会结构
    3. 设计地理/历史/文化背景
    4. 设定关键规则和限制
    5. 创建势力划分和冲突根源
    """
    
    SYSTEM_PROMPT = """你是一位资深的世界架构师，擅长创造独特而完整的小说世界。

你的任务是：
1. 根据小说类型和核心设定，构建完整的世界观
2. 确保世界观内部逻辑自洽
3. 为剧情发展预留空间
4. 创造有特色的设定，避免俗套

世界观应包含：
- 世界概述（名称、规模、基本特征）
- 力量体系（如有修仙、异能等）
- 社会结构（阶层、势力、组织）
- 地理环境（地图、主要地区）
- 历史背景（起源、重要事件）
- 文化设定（信仰、习俗、禁忌）
- 关键规则（限制、代价、能力边界）

输出必须是合法的JSON格式。"""
    
    def __init__(self, novel_id: Optional[int] = None):
        super().__init__("WorldBuilder", self.SYSTEM_PROMPT)
        self.novel_id = novel_id
        if novel_id:
            self._llm = TrackedLLMService(
                provider=LLMProvider.DEEPSEEK,
                novel_id=novel_id,
                agent_name="world_builder",
                auto_track=True
            )
            set_novel_context(novel_id)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建世界观
        
        Args:
            context: 包含 genre, demand_analysis, user_input 等
            
        Returns:
            世界观设定
        """
        novel_id = context.get("novel_id") or self.novel_id
        
        # 设置追踪上下文
        if novel_id:
            set_novel_context(novel_id)
            if not hasattr(self, '_llm') or not self._llm:
                self._llm = TrackedLLMService(
                    provider=LLMProvider.DEEPSEEK,
                    novel_id=novel_id,
                    agent_name="world_builder",
                    auto_track=True
                )
        
        genre = context.get("genre", "玄幻")
        demand_analysis = context.get("demand_analysis", "")
        user_input = context.get("user_input", "")
        
        user_input_section = ""
        if user_input and user_input.strip():
            user_input_section = f"""
【用户特别要求】
{user_input}
"""
        
        prompt = f"""请为以下小说构建世界观：

小说类型：{genre}
需求分析：{demand_analysis}
{user_input_section}

请输出JSON格式：
{{
  "world_name": "世界名称",
  "overview": "世界概述",
  "power_system": {{
    "name": "力量体系名称",
    "levels": ["等级1", "等级2"],
    "rules": "体系规则"
  }},
  "social_structure": "社会结构描述",
  "geography": "地理环境描述",
  "history": "历史背景",
  "culture": "文化设定",
  "key_rules": ["规则1", "规则2"],
  "factions": [
    {{"name": "势力名", "description": "描述", "alignment": "正/邪/中"}}
  ]
}}"""
        
        try:
            response = await self._call_llm(prompt, output_format="json")
            result = extract_json_from_response(response)
            
            if result:
                return {
                    "success": True,
                    "world_building": result
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析世界观数据"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
