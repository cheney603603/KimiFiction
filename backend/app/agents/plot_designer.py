"""
冲突与伏笔设计智能体
设计核心冲突、伏笔铺设和悬念管理
"""
import json
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response


class PlotDesignerAgent(BaseAgent):
    """
    冲突与伏笔设计智能体
    
    负责：
    1. 设计核心冲突（主线、副线）
    2. 规划伏笔的铺设时机和回收点
    3. 设计悬念和钩子
    4. 管理剧情节奏
    5. 确保伏笔与后续剧情的呼应
    """
    
    SYSTEM_PROMPT = """你是一位专业的剧情设计师，擅长设计引人入胜的冲突和伏笔。

你的任务是：
1. 设计核心冲突（内、外、群体）
2. 规划伏笔的首次出现和回收时机
3. 设计悬念和章节钩子
4. 确保冲突递进、伏笔互相关联
5. 为角色成长创造冲突空间

输出必须是合法的JSON格式。"""
    
    def __init__(self):
        super().__init__("PlotDesigner", self.SYSTEM_PROMPT)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        设计冲突和伏笔
        
        Args:
            context: 包含 world_setting, characters, demand_analysis, user_input 等
            
        Returns:
            完整的冲突和伏笔设定
        """
        world_setting = context.get("world_setting", {})
        characters = context.get("characters", [])
        demand_analysis = context.get("demand_analysis", {})
        user_input = context.get("user_input", "")
        
        self.log_action("开始设计冲突与伏笔", {
            "world": world_setting.get("world_name", ""),
            "characters": len(characters),
            "has_user_input": bool(user_input)
        })
        
        prompt = self._build_plot_prompt(world_setting, characters, demand_analysis, user_input)
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                temperature=0.75,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            result = self._extract_json(response)
            
            if result:
                self.log_action("冲突与伏笔设计完成", {
                    "main_conflicts": len(result.get("main_conflicts", [])),
                    "foreshadowing_count": len(result.get("foreshadowing_plan", [])),
                })
                
                return {
                    "success": True,
                    "plot_setting": result,
                    "_react_trace": react_result["trace"],
                }
            else:
                return {
                    "success": False,
                    "error": "JSON解析失败"
                }
                
        except Exception as e:
            self.log_action("冲突与伏笔设计失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_plot_prompt(
        self,
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
        demand_analysis: Dict[str, Any],
        user_input: str = ""
    ) -> str:
        """构建冲突和伏笔设计提示词"""
        
        # 提取主要角色
        char_summary = []
        for char in characters[:8]:
            name = char.get("name", "未知")
            role = char.get("role_type", char.get("role", "配角"))
            profile = char.get("profile", {})
            goals = profile.get("goals", [])
            goals_str = ", ".join(goals) if isinstance(goals, list) else str(goals)
            
            char_summary.append(f"- {name}（{role}）: 目标 {goals_str or '待定'}")
        
        char_str = "\n".join(char_summary) if char_summary else "无角色设定"
        
        # 核心冲突
        world_conflicts = world_setting.get("conflicts", [])
        conflicts_str = json.dumps(world_conflicts, ensure_ascii=False) if world_conflicts else "无"
        
        # 用户输入部分
        user_input_section = ""
        if user_input and user_input.strip():
            user_input_section = f"""
【用户特别要求】
用户对剧情设计的特殊要求（必须优先考虑并融入设计）：
{user_input}

以上用户要求必须体现在冲突和伏笔设计中，不要忽略用户的创意和想法。
"""
        
        prompt = f"""请为以下小说设计核心冲突和伏笔系统：

【世界观】
世界名称：{world_setting.get('world_name', '待定')}
力量体系：{json.dumps(world_setting.get('power_systems', [])[:1], ensure_ascii=False, indent=2)[:500]}
势力划分：{json.dumps(world_setting.get('social_structure', {}).get('main_factions', [])[:3], ensure_ascii=False)[:500]}

【主要角色】
{char_str}

【需求分析】
核心卖点：{demand_analysis.get('main_selling_points', '待定')}

【现有冲突设定】
{conflicts_str}
{user_input_section}

请设计完整的冲突和伏笔系统：

{{
  "core_conflicts": [
    {{
      "type": "internal/external/group",
      "name": "冲突名称",
      "parties": ["冲突方1", "冲突方2"],
      "core_issue": "核心矛盾",
      "escalation_stages": ["初期", "中期", "高潮"],
      "resolution": "解决方式",
      "chapters_range": "1-100",
      "dramatic_weight": 0.9
    }}
  ],
  
  "foreshadowing_plan": [
    {{
      "id": "fs_001",
      "title": "伏笔标题",
      "description": "伏笔内容描述",
      "first_appearance": {{
        "chapter": 5,
        "type": "subtle/direct",
        "scene": "场景描述"
      }},
      "development": ["发展1", "发展2"],
      "resolution": {{
        "chapter": 50,
        "type": "revelation/irony/climax",
        "description": "回收描述"
      }},
      "connected_elements": ["关联角色", "关联事件"],
      "importance": 0.8
    }}
  ],
  
  "mystery_system": [
    {{
      "id": "myst_001",
      "question": "核心悬念问题",
      "hint_levels": ["初期暗示", "中期线索", "高潮揭示"],
      "chapters": {{"start": 1, "reveal": 80}},
      "related_foreshadowing": ["fs_001", "fs_002"]
    }}
  ],
  
  "chapter_hooks": [
    {{
      "chapter_range": "1-10",
      "hook_type": "conflict_setup/mystery_intro/character_reveal",
      "description": "钩子描述",
      "purpose": "作用"
    }}
  ],
  
  "plot_rhythm": {{
    "act_1": {{
      "chapters": "1-30",
      "main_events": ["事件1", "事件2"],
      "pacing": "fast/slow",
      "key_hooks": ["钩子1"]
    }},
    "act_2": {{
      "chapters": "31-80",
      "main_events": ["事件1", "事件2"],
      "pacing": "alternating",
      "key_hooks": ["钩子1"]
    }},
    "act_3": {{
      "chapters": "81-100",
      "main_events": ["事件1", "事件2"],
      "pacing": "accelerating",
      "key_hooks": ["钩子1"]
    }}
  }},
  
  "character_arcs": [
    {{
      "character": "角色名",
      "starting_state": "初始状态",
      "key_conflicts": ["冲突1", "冲突2"],
      "transformation_point": "转变点章节",
      "ending_state": "最终状态"
    }}
  ]
}}"""
        
        return prompt
    
    def _extract_json(self, response: str) -> Optional[Dict[str, Any]]:
        """提取JSON - 使用通用工具"""
        result, _ = extract_json_from_response(response)
        return result
    
    async def add_foreshadowing(
        self,
        existing_plot: Dict[str, Any],
        new_foreshadowing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        添加新的伏笔到现有设定
        
        Args:
            existing_plot: 现有冲突和伏笔设定
            new_foreshadowing: 新伏笔内容
            
        Returns:
            更新后的设定
        """
        existing = existing_plot.copy()
        existing_foreshadowing = existing.get("foreshadowing_plan", [])
        
        # 生成新伏笔ID
        existing_ids = [fs.get("id", "") for fs in existing_foreshadowing]
        new_id = new_foreshadowing.get("id", f"fs_{len(existing_ids) + 1:03d}")
        while new_id in existing_ids:
            new_id = f"fs_{int(new_id.split('_')[1]) + 1:03d}"
        
        new_foreshadowing["id"] = new_id
        existing_foreshadowing.append(new_foreshadowing)
        
        existing["foreshadowing_plan"] = existing_foreshadowing
        return existing
    
    async def validate_foreshadowing_coverage(
        self,
        plot_setting: Dict[str, Any],
        chapter_outlines: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        验证伏笔在大纲中的覆盖
        
        Args:
            plot_setting: 冲突和伏笔设定
            chapter_outlines: 章节细纲列表
            
        Returns:
            验证结果
        """
        foreshadowing = plot_setting.get("foreshadowing_plan", [])
        unresolved = []
        missing_timing = []
        
        for fs in foreshadowing:
            fs_id = fs.get("id", "")
            first_ch = fs.get("first_appearance", {}).get("chapter", 0)
            resolve_ch = fs.get("resolution", {}).get("chapter", 0)
            
            # 检查是否在大纲中有体现
            found = False
            for outline in chapter_outlines:
                ch_num = outline.get("chapter_number", 0)
                content = str(outline).lower()
                
                if first_ch <= ch_num <= resolve_ch:
                    if fs_id.lower() in content or fs.get("title", "").lower() in content:
                        found = True
                        break
            
            if not found:
                unresolved.append({
                    "id": fs_id,
                    "title": fs.get("title", ""),
                    "first_chapter": first_ch,
                    "resolution_chapter": resolve_ch,
                    "issue": "未在章节大纲中找到对应内容"
                })
        
        return {
            "total_foreshadowing": len(foreshadowing),
            "unresolved_count": len(unresolved),
            "unresolved": unresolved,
            "coverage_rate": 1.0 - len(unresolved) / max(len(foreshadowing), 1),
            "is_valid": len(unresolved) == 0,
        }
    
    async def generate_chapter_hooks(
        self,
        plot_setting: Dict[str, Any],
        chapter_range: str
    ) -> List[Dict[str, Any]]:
        """
        为特定章节范围生成钩子建议
        
        Args:
            plot_setting: 冲突和伏笔设定
            chapter_range: 章节范围，如 "10-20"
            
        Returns:
            钩子建议列表
        """
        start, end = map(int, chapter_range.split("-"))
        
        # 获取该范围内的伏笔
        foreshadowing = plot_setting.get("foreshadowing_plan", [])
        relevant_fs = [
            fs for fs in foreshadowing
            if fs.get("first_appearance", {}).get("chapter", 0) in range(start, end + 1)
        ]
        
        hooks = []
        for fs in relevant_fs:
            hooks.append({
                "chapter": fs.get("first_appearance", {}).get("chapter"),
                "type": "foreshadowing",
                "foreshadowing_id": fs.get("id"),
                "title": fs.get("title"),
                "presentation": fs.get("first_appearance", {}).get("scene", ""),
            })
        
        return hooks
