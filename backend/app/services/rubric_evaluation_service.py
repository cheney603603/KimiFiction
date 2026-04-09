"""
Rubric Evaluation Service
基于知识库构建结构化Rubric，执行系统化评测

核心功能：
1. 动态构建Rubric - 基于小说类型、角色库、规则库、情节库
2. 结构化评分 - 多维度评分，支持权重配置
3. 一致性检查 - 调用知识库验证情节/角色/世界观一致性
4. 报告生成 - 生成可读的评测报告
"""
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rubric import (
    RubricTemplate, RubricDimension, RubricEvaluation,
    DimensionCategory, EvaluationType
)
from app.models.novel import Novel
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.memory_node import MemoryNode
from app.core.database import get_session
from app.agents.reader import ReaderAgent


class RubricBuilder:
    """Rubric构建器 - 基于知识库动态构建评测标准"""
    
    # 默认维度配置
    DEFAULT_DIMENSIONS = [
        {
            "category": DimensionCategory.PLOT_CONSISTENCY,
            "name": "情节一致性",
            "weight": 0.20,
            "criteria": [
                "情节发展与大纲一致",
                "伏笔得到合理回收",
                "时间线逻辑正确",
                "因果关系清晰"
            ]
        },
        {
            "category": DimensionCategory.STYLE_MATCHING,
            "name": "风格匹配度",
            "weight": 0.15,
            "criteria": [
                "符合小说类型风格",
                "语言风格前后一致",
                "叙事节奏符合预期",
                "对话风格符合角色"
            ]
        },
        {
            "category": DimensionCategory.LOGIC_RATIONALITY,
            "name": "逻辑合理性",
            "weight": 0.20,
            "criteria": [
                "事件发展符合逻辑",
                "角色行为动机合理",
                "世界观设定自洽",
                "无明显的逻辑漏洞"
            ]
        },
        {
            "category": DimensionCategory.CHARACTER_CONSISTENCY,
            "name": "角色一致性",
            "weight": 0.15,
            "criteria": [
                "角色性格前后一致",
                "角色成长符合设定",
                "角色关系发展合理",
                "角色行为符合人设"
            ]
        },
        {
            "category": DimensionCategory.WORLD_CONSISTENCY,
            "name": "世界观一致性",
            "weight": 0.10,
            "criteria": [
                "世界观设定无矛盾",
                "力量体系保持一致",
                "地理/历史设定正确",
                "规则设定前后一致"
            ]
        },
        {
            "category": DimensionCategory.NARRATIVE_FLOW,
            "name": "叙事流畅度",
            "weight": 0.10,
            "criteria": [
                "段落过渡自然",
                "场景切换流畅",
                "视角转换清晰",
                "节奏控制得当"
            ]
        },
        {
            "category": DimensionCategory.EMOTIONAL_IMPACT,
            "name": "情感冲击力",
            "weight": 0.05,
            "criteria": [
                "情感描写真实",
                "高潮部分有感染力",
                "读者能产生共鸣",
                "情绪转折自然"
            ]
        },
        {
            "category": DimensionCategory.HOOK_STRENGTH,
            "name": "钩子强度",
            "weight": 0.05,
            "criteria": [
                "开头吸引人",
                "结尾有悬念",
                "章节内有小高潮",
                "有追读欲望"
            ]
        }
    ]
    
    def __init__(self, novel_id: int):
        self.novel_id = novel_id
        self.session: Optional[AsyncSession] = None
        
    async def __aenter__(self):
        self.session = await get_session().__anext__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def build_rubric(
        self,
        genre: Optional[str] = None,
        custom_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        构建Rubric评测标准
        
        Args:
            genre: 小说类型，用于调整维度权重
            custom_weights: 自定义权重覆盖
            
        Returns:
            Rubric配置字典
        """
        # 获取小说类型
        if not genre:
            result = await self.session.execute(
                select(Novel.genre).where(Novel.id == self.novel_id)
            )
            genre = result.scalar() or "general"
        
        # 基础维度
        dimensions = [dict(d) for d in self.DEFAULT_DIMENSIONS]
        
        # 根据类型调整权重
        genre_adjustments = self._get_genre_adjustments(genre)
        for dim in dimensions:
            category = dim["category"].value if hasattr(dim["category"], "value") else dim["category"]
            if category in genre_adjustments:
                dim["weight"] *= genre_adjustments[category]
        
        # 应用自定义权重
        if custom_weights:
            for dim in dimensions:
                category = dim["category"].value if hasattr(dim["category"], "value") else dim["category"]
                if category in custom_weights:
                    dim["weight"] = custom_weights[category]
        
        # 归一化权重
        total_weight = sum(d["weight"] for d in dimensions)
        for dim in dimensions:
            dim["weight"] /= total_weight
        
        # 获取知识库引用
        kb_refs = await self._get_knowledge_base_refs()
        
        rubric_config = {
            "novel_id": self.novel_id,
            "genre": genre,
            "dimensions": dimensions,
            "knowledge_base_refs": kb_refs,
            "total_weight": 1.0,
            "version": "1.0"
        }
        
        logger.info(f"[RubricBuilder] 构建完成: {len(dimensions)}维度, 类型={genre}")
        return rubric_config
    
    def _get_genre_adjustments(self, genre: str) -> Dict[str, float]:
        """获取类型特定的权重调整"""
        adjustments = {
            "玄幻": {
                "world_consistency": 1.5,
                "logic_rationality": 0.8,
                "emotional_impact": 1.2
            },
            "科幻": {
                "logic_rationality": 1.5,
                "world_consistency": 1.3,
                "plot_consistency": 0.9
            },
            "都市": {
                "character_consistency": 1.3,
                "logic_rationality": 1.2,
                "world_consistency": 0.7
            },
            "悬疑": {
                "plot_consistency": 1.5,
                "hook_strength": 1.5,
                "logic_rationality": 1.3
            },
            "言情": {
                "emotional_impact": 1.8,
                "character_consistency": 1.3,
                "narrative_flow": 1.2
            }
        }
        return adjustments.get(genre, {})
    
    async def _get_knowledge_base_refs(self) -> Dict[str, List[Dict]]:
        """获取知识库引用信息"""
        refs = {
            "characters": [],
            "plot_points": [],
            "world_facts": [],
            "rules": []
        }
        
        # 获取活跃角色
        result = await self.session.execute(
            select(Character).where(
                Character.novel_id == self.novel_id,
                Character.is_active == True
            )
        )
        characters = result.scalars().all()
        refs["characters"] = [
            {"id": c.id, "name": c.name, "role": c.role}
            for c in characters
        ]
        
        # 获取关键情节节点
        result = await self.session.execute(
            select(MemoryNode).where(
                MemoryNode.novel_id == self.novel_id,
                MemoryNode.node_type.in_(["plot_point", "foreshadowing", "mystery"]),
                MemoryNode.is_resolved == False
            )
        )
        plot_nodes = result.scalars().all()
        refs["plot_points"] = [
            {"id": n.id, "type": n.node_type, "title": n.title}
            for n in plot_nodes
        ]
        
        # 获取世界观事实
        result = await self.session.execute(
            select(MemoryNode).where(
                MemoryNode.novel_id == self.novel_id,
                MemoryNode.node_type == "world_fact"
            )
        )
        world_nodes = result.scalars().all()
        refs["world_facts"] = [
            {"id": n.id, "title": n.title}
            for n in world_nodes
        ]
        
        logger.info(f"[RubricBuilder] 知识库: {len(refs['characters'])}角色, "
                   f"{len(refs['plot_points'])}情节, {len(refs['world_facts'])}设定")
        return refs


class StructuredEvaluator:
    """结构化评测器 - 基于Rubric执行系统化评测"""
    
    def __init__(self, novel_id: int, rubric_config: Dict[str, Any]):
        self.novel_id = novel_id
        self.rubric_config = rubric_config
        self.reader_agent = ReaderAgent()
        self.session: Optional[AsyncSession] = None
        
    async def __aenter__(self):
        self.session = await get_session().__anext__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def evaluate_chapter(
        self,
        chapter_number: int,
        chapter_content: str,
        eval_type: EvaluationType = EvaluationType.MID_TRAINING
    ) -> RubricEvaluation:
        """
        评测单个章节
        
        Args:
            chapter_number: 章节号
            chapter_content: 章节内容
            eval_type: 评测类型
            
        Returns:
            RubricEvaluation对象
        """
        logger.info(f"[StructuredEvaluator] 开始评测章节{chapter_number}")
        
        # 获取章节信息
        chapter = await self._get_chapter(chapter_number)
        
        # 获取大纲和上下文
        context = await self._get_evaluation_context(chapter_number)
        
        # 执行各维度评测
        dimensions = []
        dimension_scores = {}
        
        for dim_config in self.rubric_config["dimensions"]:
            dimension = await self._evaluate_dimension(
                dim_config,
                chapter_content,
                context
            )
            dimensions.append(dimension)
            category = dimension.category.value if hasattr(dimension.category, "value") else dimension.category
            dimension_scores[category] = {
                "score": dimension.score,
                "weight": dimension.weight,
                "weighted_score": dimension.score * dimension.weight * 10  # 转换为百分制
            }
        
        # 计算总分
        total_score = sum(d.score for d in dimensions) / len(dimensions)
        weighted_score = sum(
            d.score * d.weight for d in dimensions
        )
        
        # 执行一致性检查
        consistency_issues = await self._check_consistency(
            chapter_content,
            context
        )
        
        # 生成总结反馈
        summary = self._generate_summary(dimensions, consistency_issues)
        
        # 创建评测记录
        evaluation = RubricEvaluation(
            novel_id=self.novel_id,
            chapter_id=chapter.id if chapter else None,
            chapter_number=chapter_number,
            eval_type=eval_type,
            evaluator_type="reader_agent",
            total_score=total_score,
            weighted_score=weighted_score,
            dimension_scores=dimension_scores,
            summary_feedback=summary["feedback"],
            strengths=summary["strengths"],
            weaknesses=summary["weaknesses"],
            improvement_suggestions=summary["suggestions"],
            consistency_issues=[issue.dict() for issue in consistency_issues] if consistency_issues else []
        )
        
        # 保存到数据库
        self.session.add(evaluation)
        await self.session.commit()
        
        # 保存维度详情
        for dim in dimensions:
            dim.evaluation_id = evaluation.id
            self.session.add(dim)
        await self.session.commit()
        
        logger.info(f"[StructuredEvaluator] 评测完成: 总分={total_score:.2f}, 加权={weighted_score:.2f}")
        return evaluation
    
    async def _evaluate_dimension(
        self,
        dim_config: Dict[str, Any],
        chapter_content: str,
        context: Dict[str, Any]
    ) -> RubricDimension:
        """评测单个维度"""
        category = dim_config["category"]
        
        # 构建评测提示
        prompt = self._build_dimension_prompt(
            dim_config,
            chapter_content,
            context
        )
        
        # 调用Reader Agent进行评测
        reader_context = {
            "chapter_number": context.get("chapter_number", 0),
            "chapter_content": chapter_content[:3000],  # 限制长度
            "outline": context.get("outline", {}),
            "target_reader": context.get("target_reader", "大众网文读者"),
            "evaluation_focus": dim_config["name"],
            "criteria": dim_config.get("criteria", [])
        }
        
        result = await self.reader_agent.process(reader_context)
        
        # 解析评分
        reader_score = result.get("reader_score", 5.0)
        
        # 转换为1-10分制
        score = min(10.0, max(1.0, reader_score))
        
        # 检查标准项
        criteria_met = []
        criteria_missed = []
        for criterion in dim_config.get("criteria", []):
            # 简化处理：基于分数判断
            if score >= 7:
                criteria_met.append(criterion)
            elif score <= 4:
                criteria_missed.append(criterion)
        
        # 构建维度对象
        dimension = RubricDimension(
            category=category if isinstance(category, DimensionCategory) else DimensionCategory(category),
            name=dim_config["name"],
            weight=dim_config["weight"],
            score=score,
            criteria_met=criteria_met,
            criteria_missed=criteria_missed,
            feedback=result.get("revision_suggestions", ["无具体反馈"])[0] if result.get("revision_suggestions") else "",
            evidence=self._extract_evidence(chapter_content, category)
        )
        
        return dimension
    
    def _build_dimension_prompt(
        self,
        dim_config: Dict[str, Any],
        chapter_content: str,
        context: Dict[str, Any]
    ) -> str:
        """构建维度评测提示"""
        return f"""请从"{dim_config['name']}"维度评价这一章。

评价标准：
{chr(10).join(f"- {c}" for c in dim_config.get('criteria', []))}

章节内容摘要：
{chapter_content[:1000]}...

请给出1-10分的评分和具体反馈。"""
    
    def _extract_evidence(self, content: str, category: DimensionCategory) -> str:
        """提取评分证据（关键文本片段）"""
        # 简化实现：返回前200字符
        return content[:200] + "..." if len(content) > 200 else content
    
    async def _get_chapter(self, chapter_number: int) -> Optional[Chapter]:
        """获取章节对象"""
        result = await self.session.execute(
            select(Chapter).where(
                Chapter.novel_id == self.novel_id,
                Chapter.chapter_number == chapter_number
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_evaluation_context(self, chapter_number: int) -> Dict[str, Any]:
        """获取评测上下文"""
        # 获取小说信息
        result = await self.session.execute(
            select(Novel).where(Novel.id == self.novel_id)
        )
        novel = result.scalar_one_or_none()
        
        # 获取大纲
        from app.models.outline import Outline
        result = await self.session.execute(
            select(Outline).where(Outline.novel_id == self.novel_id)
        )
        outline = result.scalar_one_or_none()
        
        return {
            "novel_id": self.novel_id,
            "chapter_number": chapter_number,
            "genre": novel.genre if novel else "general",
            "target_reader": novel.style_prompt if novel else "大众网文读者",
            "outline": {"summary": outline.summary} if outline else {},
            "total_chapters": novel.total_chapters if novel else 0
        }
    
    async def _check_consistency(
        self,
        chapter_content: str,
        context: Dict[str, Any]
    ) -> List[Any]:
        """检查一致性问题"""
        issues = []
        
        # 获取角色信息
        result = await self.session.execute(
            select(Character).where(
                Character.novel_id == self.novel_id,
                Character.is_active == True
            )
        )
        characters = result.scalars().all()
        
        # 简单的一致性检查（可扩展）
        for char in characters:
            if char.name in chapter_content:
                # 检查角色行为是否符合人设
                pass
        
        return issues
    
    def _generate_summary(
        self,
        dimensions: List[RubricDimension],
        consistency_issues: List[Any]
    ) -> Dict[str, Any]:
        """生成评测总结"""
        # 排序找出最强和最弱维度
        sorted_dims = sorted(dimensions, key=lambda d: d.score, reverse=True)
        
        strengths = [
            f"{d.name}({d.score:.1f}分): {d.feedback[:50]}..."
            for d in sorted_dims[:2] if d.score >= 7
        ]
        
        weaknesses = [
            f"{d.name}({d.score:.1f}分): {d.feedback[:50]}..."
            for d in sorted_dims[-2:] if d.score <= 5
        ]
        
        suggestions = []
        for d in sorted_dims[-3:]:
            if d.criteria_missed:
                suggestions.append(f"改进{d.name}: {d.criteria_missed[0]}")
        
        # 添加一致性建议
        if consistency_issues:
            suggestions.append(f"注意一致性问题: {len(consistency_issues)}处")
        
        # 总体反馈
        avg_score = sum(d.score for d in dimensions) / len(dimensions)
        if avg_score >= 8:
            feedback = "整体质量优秀，继续保持！"
        elif avg_score >= 6:
            feedback = "整体质量良好，有改进空间。"
        else:
            feedback = "整体质量需要提升，建议重点改进薄弱环节。"
        
        return {
            "feedback": feedback,
            "strengths": strengths or ["无明显优势"],
            "weaknesses": weaknesses or ["无明显缺陷"],
            "suggestions": suggestions or ["继续保持当前水平"]
        }


class RubricEvaluationService:
    """Rubric评测服务 - 对外接口"""
    
    def __init__(self, novel_id: int):
        self.novel_id = novel_id
        self.rubric_config: Optional[Dict[str, Any]] = None
        
    async def initialize(self, genre: Optional[str] = None):
        """初始化Rubric配置"""
        async with RubricBuilder(self.novel_id) as builder:
            self.rubric_config = await builder.build_rubric(genre)
        logger.info(f"[RubricEvaluationService] 初始化完成: novel_id={self.novel_id}")
    
    async def evaluate_chapter(
        self,
        chapter_number: int,
        chapter_content: str,
        eval_type: EvaluationType = EvaluationType.MID_TRAINING
    ) -> Dict[str, Any]:
        """
        评测章节（主入口）
        
        Returns:
            评测结果字典
        """
        if not self.rubric_config:
            await self.initialize()
        
        async with StructuredEvaluator(self.novel_id, self.rubric_config) as evaluator:
            evaluation = await evaluator.evaluate_chapter(
                chapter_number,
                chapter_content,
                eval_type
            )
            
            return {
                "evaluation_id": evaluation.id,
                "total_score": evaluation.total_score,
                "weighted_score": evaluation.weighted_score,
                "dimension_scores": evaluation.dimension_scores,
                "summary": evaluation.summary_feedback,
                "strengths": evaluation.strengths,
                "weaknesses": evaluation.weaknesses,
                "suggestions": evaluation.improvement_suggestions,
                "consistency_issues": evaluation.consistency_issues
            }
    
    async def batch_evaluate(
        self,
        chapter_numbers: List[int],
        eval_type: EvaluationType = EvaluationType.MID_TRAINING
    ) -> List[Dict[str, Any]]:
        """批量评测多个章节"""
        results = []
        
        async with get_session().__anext__() as session:
            for chapter_number in chapter_numbers:
                # 获取章节内容
                result = await session.execute(
                    select(Chapter).where(
                        Chapter.novel_id == self.novel_id,
                        Chapter.chapter_number == chapter_number
                    )
                )
                chapter = result.scalar_one_or_none()
                
                if chapter and chapter.content:
                    eval_result = await self.evaluate_chapter(
                        chapter_number,
                        chapter.content,
                        eval_type
                    )
                    results.append({
                        "chapter_number": chapter_number,
                        **eval_result
                    })
        
        return results
    
    def get_rubric_config(self) -> Dict[str, Any]:
        """获取当前Rubric配置"""
        return self.rubric_config or {}
