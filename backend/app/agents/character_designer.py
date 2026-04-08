"""
角色设计智能体
生成详细角色卡和角色关系
"""
import json
from typing import Any, Dict, List
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response


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
    
    def __init__(self):
        super().__init__("CharacterDesigner", self.SYSTEM_PROMPT)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成角色设计
        
        Args:
            context: 包含 genre, plot_summary, num_protagonists, user_input 等
            
        Returns:
            角色设计列表
        """
        genre = context.get("genre", "玄幻")
        plot_summary = context.get("plot_summary", "")
        num_characters = context.get("num_characters", 5)
        existing_characters = context.get("existing_characters", [])
        user_input = context.get("user_input", "")
        
        self.log_action("开始角色设计", {
            "genre": genre,
            "num_characters": num_characters,
            "has_user_input": bool(user_input)
        })
        
        existing_names = ", ".join([c["name"] for c in existing_characters]) if existing_characters else "无"
        
        # 用户输入部分
        user_input_section = ""
        if user_input and user_input.strip():
            user_input_section = f"""
【用户特别要求】
用户对角色设计的特殊要求（必须优先考虑并融入设计）：
{user_input}

以上用户要求必须体现在角色设计中，不要忽略用户的创意和想法。
"""
        
        prompt = f"""请为以下小说设计角色阵容：

类型：{genre}
剧情概要：
{plot_summary}

已有角色：{existing_names}
{user_input_section}

请设计{num_characters}个角色，包括：
1. 主角（1-2位）
2. 主要反派（1-2位），可能是阶段性的，不一定是最终的反派。
3. 重要配角（2-3位）

输出JSON格式：
{{
  "characters": [
    {{
      "name": "角色名",
      "role_type": "protagonist/antagonist/supporting",
      "profile": {{
        "age": 年龄,
        "gender": "性别",
        "appearance": "外貌描述",
        "personality": "性格描述",
        "mbti": "MBTI类型",
        "background": "背景故事",
        "goals": ["目标1", "目标2"],
        "fears": ["恐惧1"],
        "skills": ["技能1", "技能2"],
        "relationships": {{"角色A": "关系描述"}}
      }},
      "arc_description": "角色成长弧线描述"
    }}
  ],
  "relationship_summary": "角色关系概述"
}}"""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                temperature=0.8,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            
            # 使用通用JSON解析工具
            result, parse_message = extract_json_from_response(response)
            
            if result is None:
                self.log_action("JSON解析失败", {"error": parse_message})
                return {
                    "success": False,
                    "error": f"JSON解析失败: {parse_message}",
                    "raw_response": response[:1000]
                }
            
            characters = result.get("characters", [])
            
            self.log_action("角色设计完成", {
                "character_count": len(characters)
            })
            
            return {
                "success": True,
                "characters": characters,
                "relationship_summary": result.get("relationship_summary", ""),
                "_react_trace": react_result["trace"],
            }
            
        except Exception as e:
            self.log_action("角色设计失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    async def design_single_character(
        self,
        role_type: str,
        genre: str,
        requirements: str = ""
    ) -> Dict[str, Any]:
        """
        设计单个角色
        
        Args:
            role_type: 角色类型
            genre: 小说类型
            requirements: 特殊要求
            
        Returns:
            单个角色设计
        """
        prompt = f"""请设计一个{role_type}类型的角色：

小说类型：{genre}
特殊要求：{requirements}

输出JSON格式。"""
        
        react_result = await self.run_react_loop(
            prompt,
            context={"agent_loop_steps": 2},
            temperature=0.8,
            output_format="json",
        )
        response = react_result["final_text"] or react_result["raw_response"]
        
        result, _ = extract_json_from_response(response)
        if result:
            return result
        return {"name": "未知角色", "error": "解析失败", "raw": response}
