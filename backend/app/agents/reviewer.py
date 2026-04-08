"""
章节审核与修改智能体
处理用户反馈，修订章节内容或调整整体框架
"""
import json
import re
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent
from app.core.json_utils import extract_json_from_response


class ReviewerAgent(BaseAgent):
    """
    章节审核与修改智能体
    
    负责：
    1. 审核章节质量（文风、节奏、逻辑）
    2. 根据用户反馈修订章节
    3. 调整整体框架（伏笔、人物弧、节奏）
    4. 保持修订一致性
    """
    
    SYSTEM_PROMPT = """你是一位资深的小说编辑，擅长发现并修复小说中的问题。

你的职责是：
1. 发现章节中的问题（逻辑漏洞、文风不一致、节奏问题）
2. 根据反馈意见修订章节
3. 调整整体框架以保持一致性
4. 确保修订后的内容与整体设定相符

输出必须是合法的JSON格式。"""
    
    # 常见问题类型
    ISSUE_TYPES = {
        "logic_inconsistency": "逻辑不一致",
        "character_inconsistency": "角色行为不一致",
        "pacing_issue": "节奏问题",
        "style_inconsistency": "文风不一致",
        "foreshadowing_missing": "伏笔未回收",
        "unresolved_hook": "悬念未解决",
        "plot_hole": "剧情漏洞",
        "info_dump": "信息堆砌",
        "weak_dialogue": "对话平淡",
        "offensive_content": "敏感内容",
    }
    
    def __init__(self):
        super().__init__("Reviewer", self.SYSTEM_PROMPT)
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        审核章节或处理修订请求
        
        Args:
            context: 包含 operation, content, feedback 等
            
        Returns:
            审核结果或修订内容
        """
        operation = context.get("operation", "review")
        
        if operation == "review":
            return await self.review_chapter(context)
        elif operation == "revise_chapter":
            return await self.revise_chapter(context)
        elif operation == "adjust_framework":
            return await self.adjust_framework(context)
        elif operation == "style_analysis":
            return await self.analyze_style(context)
        else:
            return {
                "success": False,
                "error": f"未知操作: {operation}"
            }
    
    async def review_chapter(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        审核章节
        
        Args:
            context: 包含 chapter_content, characters, plot_setting, world_setting
            
        Returns:
            审核报告
        """
        chapter_content = context.get("chapter_content", "")
        characters = context.get("characters", [])
        plot_setting = context.get("plot_setting", {})
        world_setting = context.get("world_setting", {})
        reader_feedback = context.get("reader_feedback", {})
        chapter_number = context.get("chapter_number", 0)
        
        self.log_action("开始审核章节", {"chapter": chapter_number})
        
        # 构建提示词
        prompt = self._build_review_prompt(
            chapter_content, characters, plot_setting, world_setting, chapter_number, reader_feedback
        )
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                temperature=0.3,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            result = self._extract_json(response)
            
            if result:
                # 计算总体评分
                issues = result.get("issues", [])
                quality_score = self._calculate_quality_score(issues)
                
                self.log_action("章节审核完成", {
                    "chapter": chapter_number,
                    "quality_score": quality_score,
                    "issues_count": len(issues),
                })
                
                return {
                    "success": True,
                    "chapter_number": chapter_number,
                    "quality_score": quality_score,
                    "issues": issues,
                    "suggestions": result.get("suggestions", []),
                    "strengths": result.get("strengths", []),
                    "needs_revision": quality_score < 0.7,
                    "_react_trace": react_result["trace"],
                }
            else:
                return {
                    "success": False,
                    "error": "JSON解析失败"
                }
                
        except Exception as e:
            self.log_action("章节审核失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_review_prompt(
        self,
        chapter_content: str,
        characters: List[Dict],
        plot_setting: Dict,
        world_setting: Dict,
        chapter_number: int,
        reader_feedback: Optional[Dict] = None,
    ) -> str:
        """构建审核提示词"""
        
        # 角色名称列表
        char_names = [c.get("name", "") for c in characters[:5]]
        char_str = ", ".join(char_names) or "无"
        
        # 未解伏笔
        foreshadowing = plot_setting.get("foreshadowing_plan", [])
        unresolved_fs = [
            f"第{fs.get('resolution', {}).get('chapter', '?')}章: {fs.get('title', '')}"
            for fs in foreshadowing
            if fs.get("resolution", {}).get("chapter", 0) >= chapter_number
        ][:5]
        fs_str = "\n".join(unresolved_fs) if unresolved_fs else "无"
        
        reader_feedback_text = json.dumps(reader_feedback, ensure_ascii=False) if reader_feedback else "无"

        prompt = f"""请审核第{chapter_number}章的内容：

【章节内容】（前2000字）
{chapter_content[:2000]}

【出场角色】
{char_str}

【未解伏笔】（需要在本章或后续章节中处理）
{fs_str}

【世界观关键设定】
{world_setting.get('power_systems', [{}])[0].get('name', '无')} - {world_setting.get('power_systems', [{}])[0].get('description', '')[:100]}

【读者反馈】
{reader_feedback_text}

请进行详细审核，输出JSON格式：

{{
  "chapter_number": {chapter_number},
  "quality_score": 0-1之间的评分,
  "issues": [
    {{
      "type": "问题类型",
      "severity": "critical/major/minor",
      "location": "出现位置",
      "description": "问题描述",
      "quote": "引用原文",
      "suggestion": "修改建议"
    }}
  ],
  "strengths": ["优点1", "优点2"],
  "suggestions": ["改进建议1", "改进建议2"],
  "consistency_check": {{
    "character_consistent": true/false,
    "world_rules_followed": true/false,
    "plot_continuity": true/false,
    "foreshadowing_proper": true/false
  }},
  "pacing_analysis": {{
    "opening": "开篇评价",
    "development": "发展评价",
    "climax": "高潮评价",
    "ending": "结尾评价"
  }}
}}"""
        
        return prompt
    
    async def revise_chapter(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根据反馈修订章节
        
        Args:
            context: 包含 chapter_content, feedback, characters, outline, revision_scope
            
        Returns:
            修订后的章节
        """
        chapter_content = context.get("chapter_content", "")
        feedback = context.get("feedback", "")
        characters = context.get("characters", [])
        outline = context.get("outline", {})
        chapter_number = context.get("chapter_number", 0)
        style_guide = context.get("style_guide", "")
        
        self.log_action("开始修订章节", {
            "chapter": chapter_number,
            "feedback": feedback[:100],
        })
        
        # 构建提示词
        prompt = self._build_revision_prompt(
            chapter_content, feedback, characters, outline, style_guide, chapter_number
        )
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                temperature=0.7,
                output_format="text",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            
            # 尝试解析JSON
            result = self._extract_json(response)
            
            if result:
                return {
                    "success": True,
                    "chapter_number": chapter_number,
                    "revised_content": result.get("revised_content", response),
                    "revision_summary": result.get("revision_summary", ""),
                    "changes_made": result.get("changes_made", []),
                    "_react_trace": react_result["trace"],
                }
            else:
                # 如果不是JSON，返回纯文本
                return {
                    "success": True,
                    "chapter_number": chapter_number,
                    "revised_content": response,
                    "revision_summary": "根据反馈进行了修订",
                    "changes_made": [],
                    "_react_trace": react_result["trace"],
                }
                
        except Exception as e:
            self.log_action("章节修订失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_revision_prompt(
        self,
        chapter_content: str,
        feedback: str,
        characters: List[Dict],
        outline: Dict,
        style_guide: str,
        chapter_number: int
    ) -> str:
        """构建修订提示词"""
        
        char_str = "\n".join([
            f"- {c.get('name', '')}: {c.get('profile', {}).get('personality', c.get('description', ''))}"
            for c in characters[:5]
        ]) or "无"
        
        outline_str = json.dumps(outline, ensure_ascii=False, indent=2)[:500] if outline else "无"
        
        prompt = f"""请根据以下反馈修订第{chapter_number}章：

【原始章节】
{chapter_content[:3000]}

【修改反馈】
{feedback}

【角色设定】
{char_str}

【章节大纲】
{outline_str}

【文风指导】
{style_guide or '保持原有文风，适度优化'}

修订要求：
1. 严格按照反馈意见进行修改
2. 保持章节整体结构
3. 不要添加新的问题
4. 确保与前后章节衔接自然
5. 保持角色性格一致

请输出JSON格式：
{{
  "revised_content": "修订后的完整章节内容（Markdown格式）",
  "revision_summary": "修改摘要（100字以内）",
  "changes_made": [
    {{"type": "修改类型", "description": "具体修改"}}
  ]
}}

如果反馈较为简单，可以只输出修订后的内容。"""
        
        return prompt
    
    async def adjust_framework(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根据反馈调整整体框架
        
        Args:
            context: 包含 current_outline, feedback, characters, plot_setting
            
        Returns:
            调整后的框架
        """
        current_outline = context.get("current_outline", {})
        feedback = context.get("feedback", "")
        characters = context.get("characters", [])
        plot_setting = context.get("plot_setting", {})
        chapter_number = context.get("chapter_number", 0)
        
        self.log_action("开始调整框架", {
            "chapter": chapter_number,
            "feedback": feedback[:100],
        })
        
        prompt = f"""请根据反馈调整小说框架：

【当前大纲】
{json.dumps(current_outline, ensure_ascii=False, indent=2)[:2000]}

【当前冲突伏笔设定】
{json.dumps(plot_setting, ensure_ascii=False, indent=2)[:1500]}

【用户反馈】
{feedback}

【涉及章节】
从第{chapter_number}章开始

请分析反馈并决定需要调整的内容：
1. 是否需要调整人物弧线？
2. 是否需要修改伏笔设置？
3. 是否需要调整节奏/剧情安排？
4. 是否需要修改文风定位？

输出JSON格式：
{{
  "adjustments": [
    {{
      "type": "outline/foreshadowing/character_arc/style/pacing",
      "target": "调整对象",
      "current_state": "当前状态",
      "new_state": "新状态",
      "reason": "调整原因",
      "affected_chapters": ["章节范围"]
    }}
  ],
  "revised_outline": "调整后的关键大纲内容（可以是部分）",
  "revision_plan": [
    {{"step": 1, "description": "步骤描述"}}
  ],
  "backward_compatible": true/false
}}"""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                temperature=0.7,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            result = self._extract_json(response)
            
            if result:
                self.log_action("框架调整完成", {
                    "adjustments": len(result.get("adjustments", []))
                })
                
                return {
                    "success": True,
                    "adjustments": result.get("adjustments", []),
                    "revised_outline": result.get("revised_outline", {}),
                    "revision_plan": result.get("revision_plan", []),
                    "backward_compatible": result.get("backward_compatible", False),
                    "_react_trace": react_result["trace"],
                }
            else:
                return {
                    "success": False,
                    "error": "JSON解析失败"
                }
                
        except Exception as e:
            self.log_action("框架调整失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_style(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析文风特征
        
        Args:
            context: 包含 chapters（多章内容）
            
        Returns:
            文风分析报告
        """
        chapters = context.get("chapters", [])
        if not chapters:
            return {
                "success": False,
                "error": "缺少章节内容"
            }
        
        combined_content = "\n\n".join(chapters[:3])[:5000]
        
        prompt = f"""请分析以下章节的文风特征：

{combined_content}

请输出JSON格式的文风分析：

{{
  "overall_style": "总体风格描述",
  "sentence_patterns": ["句式特点1", "特点2"],
  "vocabulary_level": "用词水平",
  "dialogue_ratio": "对话占比",
  "description_balance": "描写与对话的平衡",
  "narrative_voice": "叙事视角/口吻",
  "unique_markers": ["标志性用词/句式"],
  "tone": ["轻松/严肃/幽默/沉重等"],
  "target_audience_hint": "目标读者推测",
  "improvement_suggestions": ["改进建议1", "建议2"]
}}"""
        
        try:
            react_result = await self.run_react_loop(
                prompt,
                context=context,
                temperature=0.3,
                output_format="json",
            )
            response = react_result["final_text"] or react_result["raw_response"]
            result = self._extract_json(response)
            
            if result:
                return {
                    "success": True,
                    "style_analysis": result,
                    "_react_trace": react_result["trace"],
                }
            else:
                return {
                    "success": False,
                    "error": "JSON解析失败"
                }
                
        except Exception as e:
            self.log_action("文风分析失败", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_json(self, response: str) -> Optional[Dict[str, Any]]:
        """提取JSON - 使用通用工具"""
        result, _ = extract_json_from_response(response)
        return result
    
    def _calculate_quality_score(self, issues: List[Dict]) -> float:
        """计算质量评分"""
        if not issues:
            return 1.0
        
        weights = {
            "critical": 0.15,
            "major": 0.08,
            "minor": 0.03,
        }
        
        total_penalty = sum(weights.get(issue.get("severity", "minor"), 0.03) for issue in issues)
        
        return max(0.0, 1.0 - total_penalty)
    
    def _count_chinese_words(self, text: str) -> int:
        """统计中文字数"""
        return len(re.findall(r'[\u4e00-\u9fff]', text))
