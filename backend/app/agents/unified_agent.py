"""
统一Agent工作流基类
所有Agent使用相同的接口和流程
"""
import json
from abc import abstractmethod
from typing import Any, Dict, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger

from app.agents.base import BaseAgent
from app.agents.prompt_builder import PromptBuilder
from app.core.json_utils import extract_json_from_response


class UnifiedAgent(BaseAgent):
    """
    统一Agent工作流基类
    
    所有阶段Agent继承此类，实现统一的工作流程：
    1. 提取用户输入和上一阶段结果
    2. 使用PromptBuilder融合提示词
    3. 调用LLM生成结果
    4. 解析并返回结构化数据
    
    子类需要实现：
    - get_template(): 返回预设模板
    - parse_result(): 解析LLM响应为结构化数据
    """
    
    def __init__(self, name: str, system_prompt: str):
        super().__init__(name, system_prompt)
        self.prompt_builder = PromptBuilder()
    
    @abstractmethod
    def get_template(self, context: Dict[str, Any]) -> str:
        """
        获取预设模板
        
        Args:
            context: 上下文信息
            
        Returns:
            模板字符串
        """
        pass
    
    @abstractmethod
    def parse_result(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析LLM响应
        
        Args:
            response: LLM原始响应
            context: 上下文信息
            
        Returns:
            解析后的结构化数据
        """
        pass
    
    def extract_previous_results(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取上一阶段结果
        
        Args:
            context: 包含 previous_phase_result 的上下文
            
        Returns:
            上一阶段结果字典
        """
        # 首先尝试获取展开的上一阶段数据
        prev_results = {}
        
        # 按优先级提取关键数据
        if "demand_analysis" in context:
            prev_results["demand_analysis"] = context["demand_analysis"]
        if "world_setting" in context:
            prev_results["world_building"] = context["world_setting"]
        if "characters" in context:
            prev_results["character_design"] = {"characters": context["characters"]}
        if "plot_setting" in context:
            prev_results["plot_design"] = context["plot_setting"]
        if "outline" in context:
            prev_results["outline_draft"] = context["outline"]
        
        # 如果没有展开数据，尝试从 previous_phase_result 获取
        if not prev_results and "previous_phase_result" in context:
            prev_data = context["previous_phase_result"]
            if isinstance(prev_data, dict):
                prev_results = prev_data
        
        return prev_results
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        统一处理流程

        Args:
            context: 包含 user_input, previous_phase_result 等的上下文

        Returns:
            处理结果
        """
        try:
            # 1. 提取信息
            user_input = context.get("user_input", "")
            previous_results = self.extract_previous_results(context)
            timeout = context.get("timeout")  # 提取超时时间

            self.log_action("开始处理", {
                "has_user_input": bool(user_input),
                "previous_phases": list(previous_results.keys()),
                "timeout": timeout
            })

            # 2. 获取模板
            template = self.get_template(context)

            # 3. 使用PromptBuilder融合提示词
            self.log_action("构建融合提示词")
            prompt_data = await PromptBuilder.build_prompt(
                phase_name=self.name,
                user_input=user_input,
                previous_results=previous_results,
                template=template,
                context={"agent_name": self.name}
            )

            if not prompt_data.get("success"):
                logger.warning(f"[{self.name}] 提示词构建失败，使用基础融合")

            fused_prompt = prompt_data.get("fused_prompt", "")

            # 保存提示词构建结果供查看
            self._last_prompt_data = prompt_data

            # 4. 调用LLM，传递timeout参数
            self.log_action("调用LLM生成", {"timeout": timeout})
            llm_kwargs = {}
            if timeout:
                llm_kwargs["timeout"] = timeout

            react_result = await self.run_react_loop(
                fused_prompt,
                context=context,
                temperature=0.75,
                output_format="json",
                **llm_kwargs
            )
            response = react_result["final_text"] or react_result["raw_response"]

            debug_response_path = self._dump_debug_response(
                "generation",
                response,
                {"timeout": timeout or "", "has_user_input": bool(user_input)}
            )
            if debug_response_path:
                logger.info(f"[{self.name}] 原始响应已保存到: {debug_response_path}")

            # 5. 解析结果
            result = self.parse_result(response, context)
            result["_react_trace"] = react_result["trace"]

            # 6. 添加提示词构建信息到结果
            result["_prompt_build_info"] = {
                "user_input": user_input,
                "context_summary": prompt_data.get("context_summary", ""),
                "key_requirements": prompt_data.get("key_requirements", []),
                "template_adaptations": prompt_data.get("template_adaptations", []),
            }

            self.log_action("处理完成", {"success": result.get("success", False)})

            return result

        except Exception as e:
            logger.error(f"[{self.name}] 处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "phase": self.name
            }
    
    def _extract_json(self, response: str) -> Optional[Dict[str, Any]]:
        """提取JSON（使用通用工具）"""
        result, _ = extract_json_from_response(response)
        return result

    def _dump_debug_response(self, stage: str, response: str, extra: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """将原始响应保存到本地，便于定位 JSON 提取问题。"""
        try:
            debug_dir = Path("backend/logs/debug_llm")
            debug_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            file_path = debug_dir / f"{self.name}_{stage}_{timestamp}.txt"

            header = [
                f"agent={self.name}",
                f"stage={stage}",
                f"time={datetime.now().isoformat()}",
            ]
            if extra:
                header.extend(f"{key}={value}" for key, value in extra.items())

            file_path.write_text("\n".join(header) + "\n\n=== RESPONSE ===\n" + str(response), encoding="utf-8")
            return str(file_path)
        except Exception as exc:
            logger.warning(f"[{self.name}] 调试响应写入失败: {exc}")
            return None


class UnifiedWorldBuilderAgent(UnifiedAgent):
    """统一世界观构建Agent"""
    
    SYSTEM_PROMPT = """你是一位资深的世界架构师，擅长创造独特而完整的小说世界。

你的任务是构建完整的世界观设定，确保：
1. 世界观内部逻辑自洽
2. 与小说类型和用户需求契合
3. 为剧情发展预留空间
4. 创造有特色的设定，避免俗套

输出必须是合法的JSON格式。"""
    
    def __init__(self):
        super().__init__("WorldBuilder", self.SYSTEM_PROMPT)
    
    def get_template(self, context: Dict[str, Any]) -> str:
        genre = context.get("genre", "玄幻")
        
        return f"""请为以下{genre}小说构建完整世界观：

要求：
1. 世界概述（名称、规模、基本特征）
2. 力量体系（如有修仙、异能等）
3. 社会结构（阶层、势力、组织）
4. 地理环境（地图、主要地区）
5. 历史背景（起源、重要事件）
6. 文化设定（信仰、习俗、禁忌）
7. 关键规则（限制、代价、能力边界）

输出JSON格式：
{{
  "world_name": "世界名称",
  "overview": "世界概述",
  "power_systems": [...],
  "social_structure": {{...}},
  "geography": {{...}},
  "history": {{...}},
  "culture": {{...}},
  "key_rules": [...]
}}"""
    
    def parse_result(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        result = self._extract_json(response)
        
        if result:
            return {
                "success": True,
                "world_setting": result,
            }
        else:
            return {
                "success": False,
                "error": "JSON解析失败",
                "raw_response": response[:1000]
            }


class UnifiedCharacterDesignerAgent(UnifiedAgent):
    """统一角色设计Agent"""
    
    SYSTEM_PROMPT = """你是一位专业的角色设计师，擅长创造立体、有深度的 fictional characters。

你的任务是设计完整的角色阵容，确保：
1. 角色性格鲜明、有层次
2. 角色关系清晰、有张力
3. 角色与故事类型和世界设定契合
4. 角色有成长空间

输出必须是合法的JSON格式，包含characters数组。"""
    
    def __init__(self):
        super().__init__("CharacterDesigner", self.SYSTEM_PROMPT)

    @staticmethod
    def _extract_character_list(result: Any) -> list:
        if isinstance(result, list):
            return result
        if not isinstance(result, dict):
            return []

        for key in ("characters", "character_list", "characterList", "roles", "角色", "角色列表"):
            value = result.get(key)
            if isinstance(value, list):
                return value

        for key in ("data", "result", "output"):
            nested = result.get(key)
            if isinstance(nested, (dict, list)):
                characters = UnifiedCharacterDesignerAgent._extract_character_list(nested)
                if characters:
                    return characters

        for value in result.values():
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
                if any("name" in item or "姓名" in item or "角色名" in item for item in value):
                    return value

        return []

    @staticmethod
    def _normalize_character(item: Any) -> Dict[str, Any]:
        if not isinstance(item, dict):
            return {}

        profile = item.get("profile")
        if not isinstance(profile, dict):
            profile = {}

        basic_info = item.get("basic_info")
        if isinstance(basic_info, dict):
            profile = {**basic_info, **profile}
        if isinstance(profile.get("basic_info"), dict):
            nested_basic_info = profile.pop("basic_info")
            profile = {**nested_basic_info, **profile}

        normalized = {
            "name": item.get("name") or item.get("姓名") or item.get("角色名") or "未命名角色",
            "role_type": item.get("role_type") or item.get("role") or item.get("角色类型") or item.get("身份") or "supporting",
            "profile": profile,
        }

        arc_description = item.get("arc_description") or item.get("成长弧线") or item.get("角色弧光")
        if arc_description:
            normalized["arc_description"] = arc_description

        return normalized
    
    def get_template(self, context: Dict[str, Any]) -> str:
        genre = context.get("genre", "玄幻")
        num_characters = context.get("num_characters", 5)

        return f"""请为以下{genre}小说设计角色阵容：

要求设计{num_characters}个角色，包括：
1. 主角（1-2位）- 有详细人设和成长弧线
2. 主要反派（1-2位）- 有动机和背景
3. 重要配角（2-3位）- 有特色和功能

每个角色应包含：
- 基本信息：姓名、年龄、性别、外貌
- 性格特征：MBTI类型、核心性格、优缺点
- 背景故事：出身、经历、创伤/动机
- 目标与冲突：表面目标、深层目标、内在冲突
- 能力/技能：与类型相符的能力设定
- 人际关系：与其他角色的关系
- 成长弧线：角色在故事中的变化轨迹

**重要**：profile 字段必须是扁平结构，不能有嵌套！

输出JSON格式：
{{
  "characters": [
    {{
      "name": "角色名",
      "role_type": "protagonist/antagonist/supporting",
      "profile": {{
        "age": 20,
        "gender": "male",
        "appearance": "外貌描述",
        "personality": "性格描述",
        "mbti": "INTJ",
        "background": "背景故事",
        "goals": ["目标1", "目标2"],
        "fears": ["恐惧1"],
        "skills": ["技能1", "技能2"],
        "relationships": {{"角色B": "朋友", "角色C": "敌人"}}
      }},
      "arc_description": "成长弧线"
    }}
  ],
  "relationship_summary": "角色关系概述"
}}"""
    
    def parse_result(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        result, parse_message = extract_json_from_response(response)
        
        if result:
            raw_characters = self._extract_character_list(result)
            characters = [
                normalized
                for normalized in (self._normalize_character(item) for item in raw_characters)
                if normalized.get("name")
            ]
            relationship_summary = ""
            if isinstance(result, dict):
                relationship_summary = (
                    result.get("relationship_summary")
                    or result.get("关系概述")
                    or result.get("角色关系概述")
                    or ""
                )
            return {
                "success": bool(characters),
                "characters": characters,
                "relationship_summary": relationship_summary,
                **({} if characters else {
                    "error": "未能从模型返回结果中解析出角色列表",
                    "parse_message": parse_message,
                    "result_type": type(result).__name__,
                    "result_keys": list(result.keys()) if isinstance(result, dict) else [],
                    "raw_response": response[:1000],
                }),
            }
        else:
            return {
                "success": False,
                "error": "JSON解析失败",
                "parse_message": parse_message,
                "raw_response": response[:1000]
            }


class UnifiedPlotDesignerAgent(UnifiedAgent):
    """统一剧情设计Agent"""
    
    SYSTEM_PROMPT = """你是一位专业的剧情设计师，擅长设计引人入胜的冲突和伏笔。

你的任务是设计核心冲突和伏笔系统，确保：
1. 冲突有层次（内、外、群体）
2. 伏笔铺设合理、有回收
3. 悬念设计吸引人
4. 剧情节奏张弛有度

输出必须是合法的JSON格式。"""
    
    def __init__(self):
        super().__init__("PlotDesigner", self.SYSTEM_PROMPT)
    
    def get_template(self, context: Dict[str, Any]) -> str:
        return """请为小说设计核心冲突和伏笔系统：

要求：
1. 核心冲突（内、外、群体）
2. 伏笔规划（首次出现、发展、回收）
3. 悬念设计（问题、线索、揭示）
4. 剧情节奏（张弛有度）
5. 章节钩子（每章结尾的吸引力）

输出JSON格式：
{
  "core_conflicts": [...],
  "foreshadowing_plan": [...],
  "mystery_system": [...],
  "chapter_hooks": [...],
  "plot_rhythm": {...}
}"""
    
    def parse_result(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        result = self._extract_json(response)
        
        if result:
            return {
                "success": True,
                "plot_setting": result,
            }
        else:
            return {
                "success": False,
                "error": "JSON解析失败",
                "raw_response": response[:1000]
            }


class UnifiedOutlineGeneratorAgent(UnifiedAgent):
    """统一大纲生成Agent"""
    
    SYSTEM_PROMPT = """你是一位资深的小说大纲设计师，擅长构建长篇小说的结构。

你的任务是设计详细的三级大纲，确保：
1. 故事结构完整，有起承转合
2. 合理安排节奏，张弛有度
3. 设置足够的冲突和转折
4. 为角色成长预留空间
5. 埋设伏笔，为后续回收做准备

输出必须是合法的JSON格式。"""
    
    def __init__(self):
        super().__init__("OutlineGenerator", self.SYSTEM_PROMPT)
    
    def get_template(self, context: Dict[str, Any]) -> str:
        # 判断是否生成章节细纲（outline_detail 阶段）
        if context.get("generate_chapter_outlines"):
            outline = context.get("outline", {})
            volumes = outline.get("volumes", [])
            total_chapters = sum(v.get("target_chapters", 100) for v in volumes) or 300
            
            volumes_desc = "\n".join([
                f"- 第{v.get('volume_number')}卷: {v.get('title', '')} ({v.get('summary', '')})"
                for v in volumes[:3]
            ])
            
            return f"""请根据已有的剧情大纲，为小说的前{min(total_chapters, 20)}章生成详细的章节细纲。

已有的剧情大纲：
{json.dumps(outline, ensure_ascii=False, indent=2)[:2000]}

要求：
1. 每一章都必须包含：chapter_number(章节号), title(章节标题), summary(章节摘要, 200字左右), key_points(本章要点, 字符串数组), scenes(场景安排, 字符串数组), word_count_target(目标字数, 默认3000)
2. 情节必须严格遵循整体大纲的走向
3. 为每一章设计合理的起承转合
4. 注意章节之间的连贯性和悬念设置

请直接输出JSON数组格式，不要包含任何额外说明：
[
  {{
    "chapter_number": 1,
    "title": "第一章标题",
    "summary": "本章摘要...",
    "key_points": ["要点1", "要点2"],
    "scenes": ["场景1", "场景2"],
    "word_count_target": 3000
  }},
  ...
]"""
        
        total_volumes = context.get("total_volumes", 3)
        chapters_per_volume = context.get("chapters_per_volume", 100)
        
        return f"""请为小说生成详细大纲：

总卷数：{total_volumes}卷
每卷章节数：约{chapters_per_volume}章

要求设计三级大纲：
1. 卷级别：每卷的主题、目标、高潮
2. 剧情弧级别：每个剧情弧的起止、冲突、解决
3. 章节级别：关键章节的节点设计

输出JSON格式：
{{
  "volumes": [
    {{
      "volume_number": 1,
      "title": "卷标题",
      "theme": "本卷主题",
      "summary": "卷摘要",
      "arcs": [...],
      "key_points": "关键节点"
    }}
  ],
  "overall_arc": "整体故事弧线",
  "estimated_total_chapters": {total_volumes * chapters_per_volume}
}}"""
    
    def parse_result(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        result = self._extract_json(response)
        
        if not result:
            return {
                "success": False,
                "error": "JSON解析失败",
                "raw_response": response[:1000]
            }
        
        # outline_detail 阶段：解析为章节细纲数组
        if context.get("generate_chapter_outlines"):
            if isinstance(result, list):
                # 确保每个元素都有 chapter_number
                for idx, item in enumerate(result):
                    if isinstance(item, dict) and "chapter_number" not in item:
                        item["chapter_number"] = idx + 1
                return {
                    "success": True,
                    "chapter_outlines": result,
                }
            elif isinstance(result, dict) and "chapter_outlines" in result:
                return {
                    "success": True,
                    "chapter_outlines": result["chapter_outlines"],
                }
            else:
                return {
                    "success": False,
                    "error": "outline_detail 阶段需要返回章节细纲数组",
                    "raw_response": response[:1000]
                }
        
        # outline_draft 阶段：解析为卷大纲
        volumes = result.get("volumes", [])
        return {
            "success": True,
            "volumes": volumes,
            "overall_arc": result.get("overall_arc", ""),
            "estimated_chapters": result.get("estimated_total_chapters", 0)
        }
