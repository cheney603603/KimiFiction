"""
角色设计智能体
生成详细角色卡和角色关系
（已集成状态追踪）
"""
import json
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response
from app.services.llm_service_tracked import TrackedLLMService
from app.services.llm_service import LLMProvider
from app.core.llm_call_tracker import set_novel_context


class CharacterDesignerAgent(BaseAgent):
    """
    角色设计智能体
    
    根据小说类型和剧情需求，生成：
    - 主角详细人设
    - 反派角色
    - 重要配角
    - 角色关系图
    - 角色成长弧线
    """
    
    SYSTEM_PROMPT = """你是一位专业的角色设计师，擅长创造立体、有深度的 fictional characters。

你的任务是根据小说类型和剧情需求，设计完整的角色阵容。

每个角色应包含：
- 基本信息：姓名、年龄、性别、外貌
- 性格特征：MBTI类型、核心性格、优缺点
- 背景故事：出身、经历、创伤/动机
- 目标与冲突：表面目标、深层目标、内在冲突
- 能力/技能：与类型相符的能力设定
- 人际关系：与其他角色的关系
- 成长弧线：角色在故事中的变化轨迹

输出必须是合法的JSON格式，包含characters数组。"""
    
    def __init__(self, novel_id: Optional[int] = None):
        super().__init__("CharacterDesigner", self.SYSTEM_PROMPT)
        self.novel_id = novel_id
        if novel_id:
            self._llm = TrackedLLMService(
                provider=LLMProvider.DEEPSEEK,
                novel_id=novel_id,
                agent_name="character_designer",
                auto_track=True
            )
            set_novel_context(novel_id)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成角色设计
        
        Args:
            context: 包含 genre, plot_summary, num_protagonists, user_input 等
            
        Returns:
            角色设计列表
        """
        novel_id = context.get("novel_id") or self.novel_id
        
        # 设置追踪上下文
        if novel_id:
            set_novel_context(novel_id)
            if not hasattr(self, '_llm') or not self._llm:
                self._llm = TrackedLLMService(
                    provider=LLMProvider.DEEPSEEK,
                    novel_id=novel_id,
                    agent_name="character_designer",
                    auto_track=True
                )
        
        genre = context.get("genre", "玄幻")
        plot_summary = context.get("plot_summary", "")
        num_protagonists = context.get("num_protagonists", 1)
        num_supporting = context.get("num_supporting", 3)
        user_input = context.get("user_input", "")
        
        user_input_section = ""
        if user_input and user_input.strip():
            user_input_section = f"""
【用户特别要求】
{user_input}
"""
        
        prompt = f"""请为以下小说设计角色阵容：

小说类型：{genre}
剧情概要：{plot_summary}
主角数量：{num_protagonists}人
重要配角数量：{num_supporting}人
{user_input_section}

请输出JSON格式：
{{
  "characters": [
    {{
      "name": "角色名",
      "role_type": "protagonist/antagonist/supporting",
      "profile": {{
        "age": "年龄",
        "gender": "性别",
        "appearance": "外貌描述",
        "mbti": "MBTI类型",
        "personality": "性格特征",
        "background": "背景故事",
        "goals": ["目标1", "目标2"],
        "fears": ["恐惧1"],
        "skills": ["技能1", "技能2"],
        "relationships": {{"角色A": "关系描述"}},
        "character_arc": "成长弧线"
      }}
    }}
  ]
}}"""
        
        try:
            response = await self._call_llm(prompt, output_format="json")
            result = extract_json_from_response(response)
            
            if result and "characters" in result:
                return {
                    "success": True,
                    "characters": result["characters"]
                }
            else:
                return {
                    "success": False,
                    "error": "无法解析角色数据"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
