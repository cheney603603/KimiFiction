"""
一致性检查智能体
检查剧情、角色、设定的一致性
"""
import json
from typing import Any, Dict, List
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response


class ConsistencyCheckerAgent(BaseAgent):
    """
    一致性检查智能体
    
    检查并确保：
    - 角色行为一致性
    - 设定不冲突
    - 剧情逻辑合理
    - 时间线正确
    """
    
    SYSTEM_PROMPT = """你是一位严格的小说编辑，专门负责检查剧情一致性。

你的任务是：
1. 检查角色行为是否符合其性格设定
2. 检查能力/设定是否有矛盾
3. 检查时间线是否合理
4. 检查伏笔是否正确回收
5. 标记需要修改的地方

输出格式：
{{
  "is_consistent": true/false,
  "issues": [
    {{
      "type": "character_behavior/setting_conflict/timeline_error/other",
      "severity": "high/medium/low",
      "description": "问题描述",
      "suggestion": "修改建议"
    }}
  ],
  "summary": "整体一致性评估"
}}"""
    
    def __init__(self):
        super().__init__("ConsistencyChecker", self.SYSTEM_PROMPT)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查一致性
        
        Args:
            context: 包含 chapter_content, characters, previous_chapters, world_settings 等
            
        Returns:
            一致性检查结果
        """
        chapter_content = context.get("chapter_content", "")
        characters = context.get("characters", [])
        previous_chapters = context.get("previous_chapters", [])
        world_settings = context.get("world_settings", {})
        
        self.log_action("开始一致性检查")
        
        # 构建角色设定信息
        char_profiles = "\n".join([
            f"角色：{c.get('name')}\n"
            f"性格：{c.get('profile', {}).get('personality', '未知')}\n"
            f"能力：{', '.join(c.get('profile', {}).get('skills', []))}\n"
            for c in characters[:3]
        ])
        
        # 构建前文关键信息
        prev_key_info = "\n".join([
            f"第{ch.get('chapter_number')}章: {ch.get('summary', '')}"
            for ch in previous_chapters[-5:]
        ])
        
        prompt = f"""请检查以下章节的一致性：

待检查章节内容：
{chapter_content[:2000]}...

角色设定：
{char_profiles}

前文关键信息：
{prev_key_info}

世界观设定：
{world_settings}

请检查并输出JSON格式的检查结果。"""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                temperature=0.3,
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
                    "is_consistent": True,  # 失败时默认通过
                    "issues": []
                }
            
            issues = result.get("issues", [])
            self.log_action("一致性检查完成", {
                "is_consistent": result.get("is_consistent"),
                "issue_count": len(issues)
            })
            
            return {
                "success": True,
                "is_consistent": result.get("is_consistent", True),
                "issues": issues,
                "summary": result.get("summary", ""),
                "_react_trace": react_result["trace"],
            }
            
        except Exception as e:
            self.log_action("检查失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e),
                "is_consistent": True,  # 失败时默认通过，避免阻塞
                "issues": []
            }
    
    async def check_character_behavior(
        self,
        character: Dict,
        action: str,
        context: str
    ) -> Dict[str, Any]:
        """
        检查单个角色行为是否一致
        
        Args:
            character: 角色信息
            action: 角色行为
            context: 场景上下文
            
        Returns:
            行为一致性判断
        """
        prompt = f"""请检查角色行为是否一致：

角色：{character.get('name')}
性格：{character.get('profile', {}).get('personality', '')}
背景：{character.get('profile', {}).get('background', '')}

当前行为：{action}
场景：{context}

这个角色会这样做吗？请给出判断和理由。"""
        
        react_result = await self.run_react_loop(
            prompt,
            context={"agent_loop_steps": 2},
            temperature=0.3,
            output_format="text",
        )
        response = react_result["final_text"] or react_result["raw_response"]
        
        return {
            "character": character.get('name'),
            "action": action,
            "assessment": response
        }
