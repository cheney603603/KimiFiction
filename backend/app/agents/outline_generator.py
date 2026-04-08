"""
大纲生成智能体
生成三级大纲结构
"""
import json
from typing import Any, Dict, List
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response


class OutlineGeneratorAgent(BaseAgent):
    """
    大纲生成智能体
    
    根据小说类型、角色和剧情需求，生成：
    - 分卷大纲
    - 剧情弧设计
    - 章节节点规划
    - 关键转折点
    - 伏笔埋设计划
    """
    
    SYSTEM_PROMPT = """你是一位资深的小说大纲设计师，擅长构建长篇小说的结构。

你的任务是设计详细的三级大纲：
- 卷级别：每卷的主题、目标、高潮
- 剧情弧级别：每个剧情弧的起止、冲突、解决
- 章节级别：关键章节的节点设计

设计原则：
1. 确保故事结构完整，有起承转合
2. 合理安排节奏，张弛有度
3. 设置足够的冲突和转折
4. 为角色成长预留空间
5. 埋设伏笔，为后续回收做准备

输出必须是合法的JSON格式。"""
    
    def __init__(self):
        super().__init__("OutlineGenerator", self.SYSTEM_PROMPT)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成大纲
        
        Args:
            context: 包含 genre, characters, plot_summary, total_volumes, user_input 等
            
        Returns:
            完整大纲结构
        """
        genre = context.get("genre", "玄幻")
        characters = context.get("characters", [])
        plot_summary = context.get("plot_summary", "")
        total_volumes = context.get("total_volumes", 3)
        chapters_per_volume = context.get("chapters_per_volume", 100)
        user_input = context.get("user_input", "")
        
        self.log_action("开始生成大纲", {
            "genre": genre,
            "volumes": total_volumes,
            "chapters_per_volume": chapters_per_volume,
            "has_user_input": bool(user_input)
        })
        
        # 构建角色信息
        char_info = "\n".join([
            f"- {c.get('name', '未知')} ({c.get('role_type', '未知')}): {c.get('profile', {}).get('personality', '')[:50]}"
            for c in characters[:5]  # 只取前5个主要角色
        ])
        
        # 用户输入部分
        user_input_section = ""
        if user_input and user_input.strip():
            user_input_section = f"""
【用户特别要求】
用户对大纲设计的特殊要求（必须优先考虑并融入设计）：
{user_input}

以上用户要求必须体现在大纲设计中，不要忽略用户的创意和想法。
"""
        
        prompt = f"""请为以下小说生成详细大纲：

类型：{genre}
总卷数：{total_volumes}卷
每卷章节数：约{chapters_per_volume}章

主要角色：
{char_info}

剧情概要：
{plot_summary}
{user_input_section}

请生成JSON格式的大纲：
{{
  "volumes": [
    {{
      "volume_number": 1,
      "title": "卷标题",
      "theme": "本卷主题",
      "summary": "卷摘要",
      "target_chapters": {chapters_per_volume},
      "arcs": [
        {{
          "arc_id": "arc_1",
          "title": "剧情弧标题",
          "description": "剧情描述",
          "start_chapter": 1,
          "end_chapter": 20,
          "key_events": ["事件1", "事件2", "事件3"],
          "conflict": "冲突描述",
          "resolution": "解决方式",
          "cliffhanger": "悬念设置（可选）"
        }}
      ],
      "key_points": "本卷关键节点概述",
      "foreshadowing": ["伏笔1", "伏笔2"]
    }}
  ],
  "overall_arc": "整体故事弧线",
  "estimated_total_chapters": {total_volumes * chapters_per_volume}
}}"""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                temperature=0.7,
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
            
            volumes = result.get("volumes", [])
            
            self.log_action("大纲生成完成", {
                "volumes": len(volumes),
                "total_arcs": sum(len(v.get("arcs", [])) for v in volumes)
            })
            
            return {
                "success": True,
                "volumes": volumes,
                "overall_arc": result.get("overall_arc", ""),
                "estimated_chapters": result.get("estimated_total_chapters", 0),
                "_react_trace": react_result["trace"],
            }
            
        except Exception as e:
            self.log_action("大纲生成失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_chapter_outline(
        self,
        volume_number: int,
        chapter_number: int,
        arc_context: Dict,
        characters: List[Dict]
    ) -> Dict[str, Any]:
        """
        生成单章大纲
        
        Args:
            volume_number: 卷号
            chapter_number: 章节号
            arc_context: 所属剧情弧信息
            characters: 相关角色
            
        Returns:
            单章大纲
        """
        prompt = f"""请为第{volume_number}卷第{chapter_number}章生成详细大纲：

剧情弧：{arc_context.get('title', '')}
剧情描述：{arc_context.get('description', '')}

输出JSON格式：
{{
  "title": "章节标题",
  "summary": "章节摘要",
  "key_events": ["事件1", "事件2"],
  "characters_present": ["角色A", "角色B"],
  "scene_setting": "场景设定",
  "emotional_arc": "情感弧线",
  "cliffhanger_score": 0.7,
  "word_count_target": 3000
}}"""
        
        react_result = await self.run_react_loop(
            prompt,
            context={"agent_loop_steps": 2},
            temperature=0.7,
            output_format="json",
        )
        response = react_result["final_text"] or react_result["raw_response"]
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            return json.loads(response)
        except:
            return {
                "title": f"第{chapter_number}章",
                "summary": "生成失败",
                "error": "解析失败"
            }
