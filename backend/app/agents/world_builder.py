"""
世界观构建智能体
根据小说类型和需求，构建完整的世界观设定
"""
import json
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response


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
    
    def __init__(self):
        super().__init__("WorldBuilder", self.SYSTEM_PROMPT)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建世界观
        
        Args:
            context: 包含 genre, demand_analysis, user_input 等
            
        Returns:
            完整的世界观设定
        """
        genre = context.get("genre", "玄幻")
        demand_analysis = context.get("demand_analysis", {})
        user_input = context.get("user_input", "")
        
        self.log_action("开始构建世界观", {"genre": genre, "has_user_input": bool(user_input)})
        
        # 构建提示词
        prompt = self._build_world_prompt(genre, demand_analysis, user_input)
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                temperature=0.75,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            
            # 清理JSON
            result = self._extract_json(response)
            
            if result:
                self.log_action("世界观构建完成", {
                    "world_name": result.get("world_name", ""),
                    "systems_count": len(result.get("power_systems", [])),
                })
                
                return {
                    "success": True,
                    "world_setting": result,
                    "_react_trace": react_result["trace"],
                }
            else:
                return {
                    "success": False,
                    "error": "JSON解析失败"
                }
                
        except Exception as e:
            self.log_action("世界观构建失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_world_prompt(self, genre: str, demand_analysis: Dict[str, Any], user_input: str = "") -> str:
        """构建世界观提示词"""
        
        # 提取核心卖点
        main_selling_points = demand_analysis.get("main_selling_points", [])
        selling_str = ", ".join(main_selling_points) if isinstance(main_selling_points, list) else str(main_selling_points)
        
        # 核心设定
        core_settings = demand_analysis.get("core_settings", [])
        settings_str = ", ".join(core_settings) if isinstance(core_settings, list) else str(core_settings)
        
        # 用户输入部分
        user_input_section = ""
        if user_input and user_input.strip():
            user_input_section = f"""
【用户特别要求】
用户对世界观的特殊要求（必须优先考虑并融入设计）：
{user_input}

以上用户要求必须体现在世界观设计中，不要忽略用户的创意和想法。
"""
        
        prompt = f"""请为以下{genre}小说构建完整世界观：

类型：{genre}
核心卖点：{selling_str or '待定'}
核心设定：{settings_str or '待定'}
{user_input_section}

请生成JSON格式的世界观设定：
{{
  "world_name": "世界名称",
  "overview": "世界概述（100字以内）",
  "genre_type": "{genre}",
  
  "power_systems": [
    {{
      "name": "力量体系名称",
      "description": "力量体系描述",
      "levels": ["等级1", "等级2", "等级3"],
      "cultivation_method": "修炼方式（如适用）",
      "rules": ["规则1", "规则2"],
      "limits": ["限制1", "限制2"]
    }}
  ],
  
  "social_structure": {{
    "main_factions": [
      {{
        "name": "势力名称",
        "description": "势力描述",
        "align": "善/中/恶",
        "resources": ["资源1", "资源2"]
      }}
    ],
    "social_classes": ["阶层1", "阶层2"],
    "power_distribution": "权力分布描述"
  }},
  
  "geography": {{
    "map_description": "地图总体描述",
    "regions": [
      {{
        "name": "地区名称",
        "description": "地区描述",
        "climate": "气候",
        "resources": ["资源"],
        "controlled_by": "控制势力"
      }}
    ]
  }},
  
  "history": {{
    "origin": "世界起源（200字以内）",
    "major_events": [
      {{
        "event": "事件名称",
        "time": "发生时间",
        "description": "事件描述",
        "impact": "影响"
      }}
    ]
  }},
  
  "culture": {{
    "beliefs": ["信仰1", "信仰2"],
    "customs": ["习俗1", "习俗2"],
    "taboos": ["禁忌1", "禁忌2"],
    "language_notes": "语言特点"
  }},
  
  "key_rules": [
    {{
      "rule": "规则名称",
      "description": "规则描述",
      "dramatic_potential": "戏剧潜力"
    }}
  ],
  
  "conflicts": [
    {{
      "type": "冲突类型",
      "parties": ["冲突方1", "冲突方2"],
      "core_issue": "核心问题",
      "current_status": "当前状态"
    }}
  ],
  
  "unique_features": ["独特设定1", "独特设定2"],
  "avoid_clichés": ["避免的俗套1", "避免的俗套2"]
}}"""
        
        return prompt
    
    def _extract_json(self, response: str) -> Optional[Dict[str, Any]]:
        """提取JSON - 使用通用工具"""
        result, _ = extract_json_from_response(response)
        return result
    
    async def expand_region(
        self,
        region_name: str,
        world_setting: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        扩展特定地区的详细设定
        
        Args:
            region_name: 地区名称
            world_setting: 现有世界观设定
            
        Returns:
            扩展后的地区设定
        """
        prompt = f"""请详细扩展以下地区的设定：

地区名称：{region_name}

现有世界观：
{json.dumps(world_setting, ensure_ascii=False, indent=2)[:2000]}

请生成更详细的地区设定，包括：
- 地形地貌
- 重要城市
- 势力分布
- 特有资源/特产
- 当地文化特色
- 可能的剧情场景

输出JSON格式。"""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context={"agent_loop_steps": 2},
                temperature=0.7,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            return self._extract_json(response) or {}
        except Exception as e:
            self.log_action("地区扩展失败", {"error": str(e)})
            return {}
    
    async def design_power_system(
        self,
        system_name: str,
        genre: str
    ) -> Dict[str, Any]:
        """
        设计完整的力量体系
        
        Args:
            system_name: 体系名称
            genre: 小说类型
            
        Returns:
            力量体系详细设定
        """
        prompt = f"""请为{genre}小说设计一套独特的力量体系：

体系名称：{system_name}
小说类型：{genre}

要求：
1. 独特且有创意，避免俗套
2. 有明确的等级划分
3. 有代价/限制机制
4. 与世界设定契合
5. 为剧情冲突预留空间

输出JSON格式。"""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context={"agent_loop_steps": 2},
                temperature=0.8,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            return self._extract_json(response) or {}
        except Exception as e:
            self.log_action("力量体系设计失败", {"error": str(e)})
            return {}
    
    async def validate_consistency(
        self,
        world_setting: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证世界观内部一致性
        
        Args:
            world_setting: 世界观设定
            
        Returns:
            一致性检查结果
        """
        prompt = f"""请检查以下世界观设定是否存在逻辑矛盾或不一致之处：

{json.dumps(world_setting, ensure_ascii=False, indent=2)[:3000]}

请识别：
1. 力量体系内部矛盾
2. 社会结构与力量体系冲突
3. 历史时间线矛盾
4. 地理设置不合理之处
5. 文化设定自相矛盾
6. 其他逻辑问题

输出JSON格式：
{{
  "is_consistent": true/false,
  "issues": [
    {{
      "type": "矛盾类型",
      "description": "问题描述",
      "location": "出现位置",
      "suggestion": "修改建议"
    }}
  ],
  "overall_assessment": "整体评价"
}}"""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context={"agent_loop_steps": 2},
                temperature=0.3,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            return self._extract_json(response) or {
                "is_consistent": True,
                "issues": [],
                "overall_assessment": "未完成检查"
            }
        except Exception as e:
            self.log_action("一致性检查失败", {"error": str(e)})
            return {
                "is_consistent": False,
                "issues": [{"type": "error", "description": str(e)}],
                "overall_assessment": "检查失败"
            }
