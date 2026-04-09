"""
Training Data Collector
RL训练数据采集器 - 保存每一轮的状态、动作、奖励数据

核心功能：
1. 实时采集 - 记录Writer-Reader RL循环的每一步
2. 数据持久化 - 保存到数据库和JSON文件
3. 前后对比 - 训练前后的Rubric评测
4. 报告生成 - 可视化训练效果
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rubric import (
    TrainingEpisode, TrainingBatch, ComparisonReport,
    RubricEvaluation, EvaluationType
)
from app.models.novel import Novel
from app.models.chapter import Chapter
from app.core.database import get_session
from app.services.rubric_evaluation_service import RubricEvaluationService


class TrainingDataCollector:
    """训练数据采集器"""
    
    def __init__(
        self,
        novel_id: int,
        project_path: str,
        batch_name: Optional[str] = None
    ):
        self.novel_id = novel_id
        self.project_path = Path(project_path)
        self.batch_name = batch_name or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 数据目录
        self.data_dir = self.project_path / "training_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.batch_dir = self.data_dir / self.batch_name
        self.batch_dir.mkdir(parents=True, exist_ok=True)
        
        # 子目录
        self.episodes_dir = self.batch_dir / "episodes"
        self.episodes_dir.mkdir(exist_ok=True)
        
        self.evaluations_dir = self.batch_dir / "evaluations"
        self.evaluations_dir.mkdir(exist_ok=True)
        
        self.reports_dir = self.batch_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        self.batch_id: Optional[int] = None
        self.session: Optional[AsyncSession] = None
        
        logger.info(f"[TrainingDataCollector] 初始化: novel_id={novel_id}, batch={self.batch_name}")
    
    async def __aenter__(self):
        self.session = await get_session().__anext__()
        await self._create_batch_record()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self._update_batch_stats()
            await self.session.close()
    
    async def _create_batch_record(self):
        """创建批次记录"""
        batch = TrainingBatch(
            batch_name=self.batch_name,
            batch_type="ppo",
            status="collecting"
        )
        self.session.add(batch)
        await self.session.commit()
        self.batch_id = batch.id
        
        logger.info(f"[TrainingDataCollector] 创建批次: id={self.batch_id}")
    
    async def _update_batch_stats(self):
        """更新批次统计"""
        if not self.batch_id:
            return
        
        result = await self.session.execute(
            select(TrainingEpisode).where(
                TrainingEpisode.novel_id == self.novel_id
            )
        )
        episodes = result.scalars().all()
        
        if episodes:
            rewards = [e.reward for e in episodes]
            batch = await self.session.get(TrainingBatch, self.batch_id)
            if batch:
                batch.episode_count = len(episodes)
                batch.avg_reward = sum(rewards) / len(rewards)
                batch.best_reward = max(rewards)
                batch.worst_reward = min(rewards)
                await self.session.commit()
    
    async def collect_episode(
        self,
        chapter_number: int,
        episode_number: int,
        round_number: int,
        state_draft: str,
        action_taken: str,
        action_probs: Dict[str, float],
        reward: float,
        reader_score: Optional[float] = None,
        hook_score: Optional[float] = None,
        immersion_score: Optional[float] = None,
        rubric_evaluation_id: Optional[int] = None,
        rubric_score: Optional[float] = None,
        policy_version: int = 0,
        is_terminal: bool = False,
        termination_reason: Optional[str] = None
    ) -> TrainingEpisode:
        """
        采集单个回合数据
        
        Args:
            chapter_number: 章节号
            episode_number: 回合序号
            round_number: 当前轮次
            state_draft: 当前草稿状态
            action_taken: 采取的动作
            action_probs: 动作概率分布
            reward: 即时奖励
            reader_score: 读者评分
            hook_score: 钩子评分
            immersion_score: 沉浸感评分
            rubric_evaluation_id: Rubric评测ID
            rubric_score: Rubric总分
            policy_version: 策略版本
            is_terminal: 是否终止
            termination_reason: 终止原因
            
        Returns:
            TrainingEpisode对象
        """
        # 计算累积奖励
        cumulative_reward = reward
        if episode_number > 1:
            result = await self.session.execute(
                select(TrainingEpisode.cumulative_reward).where(
                    TrainingEpisode.novel_id == self.novel_id,
                    TrainingEpisode.chapter_number == chapter_number,
                    TrainingEpisode.episode_number == episode_number - 1
                )
            )
            prev_cumulative = result.scalar_one_or_none()
            if prev_cumulative is not None:
                cumulative_reward += prev_cumulative
        
        episode = TrainingEpisode(
            novel_id=self.novel_id,
            chapter_number=chapter_number,
            episode_number=episode_number,
            round_number=round_number,
            state_draft=state_draft,
            state_version=len(state_draft),  # 简化版本号
            action_taken=action_taken,
            action_probs=action_probs,
            reward=reward,
            cumulative_reward=cumulative_reward,
            reader_score=reader_score,
            hook_score=hook_score,
            immersion_score=immersion_score,
            rubric_evaluation_id=rubric_evaluation_id,
            rubric_score=rubric_score,
            policy_version=policy_version,
            is_terminal=is_terminal,
            termination_reason=termination_reason
        )
        
        self.session.add(episode)
        await self.session.commit()
        
        # 保存到JSON文件
        await self._save_episode_to_file(episode)
        
        logger.info(f"[TrainingDataCollector] 采集回合: episode={episode_number}, "
                   f"chapter={chapter_number}, reward={reward:.4f}")
        
        return episode
    
    async def _save_episode_to_file(self, episode: TrainingEpisode):
        """保存回合数据到JSON文件"""
        episode_data = {
            "id": episode.id,
            "novel_id": episode.novel_id,
            "chapter_number": episode.chapter_number,
            "episode_number": episode.episode_number,
            "round_number": episode.round_number,
            "state": {
                "draft_preview": episode.state_draft[:500] + "..." if len(episode.state_draft) > 500 else episode.state_draft,
                "version": episode.state_version
            },
            "action": {
                "taken": episode.action_taken,
                "probs": episode.action_probs
            },
            "reward": {
                "immediate": episode.reward,
                "cumulative": episode.cumulative_reward
            },
            "scores": {
                "reader": episode.reader_score,
                "hook": episode.hook_score,
                "immersion": episode.immersion_score,
                "rubric": episode.rubric_score
            },
            "policy_version": episode.policy_version,
            "is_terminal": episode.is_terminal,
            "termination_reason": episode.termination_reason,
            "created_at": episode.created_at.isoformat() if episode.created_at else None
        }
        
        file_path = self.episodes_dir / f"episode_{episode.episode_number:04d}_ch{episode.chapter_number:03d}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(episode_data, f, ensure_ascii=False, indent=2)
    
    async def evaluate_before_training(
        self,
        chapter_numbers: List[int]
    ) -> Dict[str, Any]:
        """
        训练前评测 - 建立基线
        
        Args:
            chapter_numbers: 要评测的章节列表
            
        Returns:
            评测结果汇总
        """
        logger.info(f"[TrainingDataCollector] 开始训练前评测: {len(chapter_numbers)}章节")
        
        rubric_service = RubricEvaluationService(self.novel_id)
        await rubric_service.initialize()
        
        results = []
        total_score = 0.0
        
        for chapter_number in chapter_numbers:
            # 获取章节内容
            result = await self.session.execute(
                select(Chapter).where(
                    Chapter.novel_id == self.novel_id,
                    Chapter.chapter_number == chapter_number
                )
            )
            chapter = result.scalar_one_or_none()
            
            if not chapter or not chapter.content:
                logger.warning(f"[TrainingDataCollector] 章节{chapter_number}无内容，跳过")
                continue
            
            # 执行Rubric评测
            eval_result = await rubric_service.evaluate_chapter(
                chapter_number=chapter_number,
                chapter_content=chapter.content,
                eval_type=EvaluationType.PRE_TRAINING
            )
            
            results.append({
                "chapter_number": chapter_number,
                **eval_result
            })
            
            total_score += eval_result.get("weighted_score", 0)
            
            # 保存评测结果到文件
            await self._save_evaluation_to_file(
                chapter_number,
                eval_result,
                "pre_training"
            )
        
        avg_score = total_score / len(results) if results else 0.0
        
        summary = {
            "eval_type": "pre_training",
            "chapter_count": len(results),
            "average_score": avg_score,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        # 保存汇总
        summary_path = self.evaluations_dir / "pre_training_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # 更新批次记录
        if self.batch_id and results:
            batch = await self.session.get(TrainingBatch, self.batch_id)
            if batch:
                batch.pre_training_eval_id = results[0].get("evaluation_id")
        
        logger.info(f"[TrainingDataCollector] 训练前评测完成: 平均分={avg_score:.2f}")
        return summary
    
    async def evaluate_after_training(
        self,
        chapter_numbers: List[int]
    ) -> Dict[str, Any]:
        """
        训练后评测 - 评估改进
        
        Args:
            chapter_numbers: 要评测的章节列表
            
        Returns:
            评测结果汇总
        """
        logger.info(f"[TrainingDataCollector] 开始训练后评测: {len(chapter_numbers)}章节")
        
        rubric_service = RubricEvaluationService(self.novel_id)
        await rubric_service.initialize()
        
        results = []
        total_score = 0.0
        
        for chapter_number in chapter_numbers:
            result = await self.session.execute(
                select(Chapter).where(
                    Chapter.novel_id == self.novel_id,
                    Chapter.chapter_number == chapter_number
                )
            )
            chapter = result.scalar_one_or_none()
            
            if not chapter or not chapter.content:
                continue
            
            eval_result = await rubric_service.evaluate_chapter(
                chapter_number=chapter_number,
                chapter_content=chapter.content,
                eval_type=EvaluationType.POST_TRAINING
            )
            
            results.append({
                "chapter_number": chapter_number,
                **eval_result
            })
            
            total_score += eval_result.get("weighted_score", 0)
            
            await self._save_evaluation_to_file(
                chapter_number,
                eval_result,
                "post_training"
            )
        
        avg_score = total_score / len(results) if results else 0.0
        
        summary = {
            "eval_type": "post_training",
            "chapter_count": len(results),
            "average_score": avg_score,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        summary_path = self.evaluations_dir / "post_training_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # 更新批次记录
        if self.batch_id and results:
            batch = await self.session.get(TrainingBatch, self.batch_id)
            if batch:
                batch.post_training_eval_id = results[0].get("evaluation_id")
                batch.status = "completed"
                batch.completed_at = datetime.now()
                await self.session.commit()
        
        logger.info(f"[TrainingDataCollector] 训练后评测完成: 平均分={avg_score:.2f}")
        return summary
    
    async def _save_evaluation_to_file(
        self,
        chapter_number: int,
        eval_result: Dict[str, Any],
        eval_type: str
    ):
        """保存单个评测结果到文件"""
        file_path = self.evaluations_dir / f"{eval_type}_ch{chapter_number:03d}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(eval_result, f, ensure_ascii=False, indent=2)
    
    async def generate_comparison_report(
        self,
        pre_training_summary: Dict[str, Any],
        post_training_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成训练前后对比报告
        
        Args:
            pre_training_summary: 训练前评测汇总
            post_training_summary: 训练后评测汇总
            
        Returns:
            对比报告
        """
        logger.info("[TrainingDataCollector] 生成对比报告")
        
        pre_score = pre_training_summary.get("average_score", 0)
        post_score = post_training_summary.get("average_score", 0)
        improvement = post_score - pre_score
        improvement_rate = (improvement / pre_score * 100) if pre_score > 0 else 0
        
        # 章节级对比
        chapter_comparisons = []
        pre_results = {r["chapter_number"]: r for r in pre_training_summary.get("results", [])}
        post_results = {r["chapter_number"]: r for r in post_training_summary.get("results", [])}
        
        for ch_num in set(pre_results.keys()) & set(post_results.keys()):
            pre = pre_results[ch_num]
            post = post_results[ch_num]
            
            chapter_comparisons.append({
                "chapter_number": ch_num,
                "pre_score": pre.get("weighted_score", 0),
                "post_score": post.get("weighted_score", 0),
                "improvement": post.get("weighted_score", 0) - pre.get("weighted_score", 0),
                "pre_strengths": pre.get("strengths", []),
                "post_strengths": post.get("strengths", []),
                "pre_weaknesses": pre.get("weaknesses", []),
                "post_weaknesses": post.get("weaknesses", [])
            })
        
        # 维度级对比
        dimension_improvements = {}
        for ch_comp in chapter_comparisons:
            pre_dims = pre_results[ch_comp["chapter_number"]].get("dimension_scores", {})
            post_dims = post_results[ch_comp["chapter_number"]].get("dimension_scores", {})
            
            for dim_name in set(pre_dims.keys()) & set(post_dims.keys()):
                if dim_name not in dimension_improvements:
                    dimension_improvements[dim_name] = []
                
                pre_dim_score = pre_dims[dim_name].get("weighted_score", 0)
                post_dim_score = post_dims[dim_name].get("weighted_score", 0)
                dimension_improvements[dim_name].append(post_dim_score - pre_dim_score)
        
        # 计算平均维度改进
        avg_dimension_improvements = {
            dim: sum(improvements) / len(improvements)
            for dim, improvements in dimension_improvements.items()
            if improvements
        }
        
        # 找出改进最大和最小的维度
        sorted_dims = sorted(avg_dimension_improvements.items(), key=lambda x: x[1], reverse=True)
        best_improved = sorted_dims[:3] if sorted_dims else []
        worst_improved = sorted_dims[-3:] if sorted_dims else []
        
        report = {
            "report_name": f"Training_Comparison_{self.batch_name}",
            "batch_name": self.batch_name,
            "novel_id": self.novel_id,
            "summary": {
                "pre_training_score": pre_score,
                "post_training_score": post_score,
                "absolute_improvement": improvement,
                "improvement_rate": f"{improvement_rate:.1f}%",
                "chapter_count": len(chapter_comparisons)
            },
            "dimension_analysis": {
                "average_improvements": avg_dimension_improvements,
                "best_improved_dimensions": [
                    {"dimension": dim, "improvement": imp} for dim, imp in best_improved
                ],
                "needs_attention_dimensions": [
                    {"dimension": dim, "improvement": imp} for dim, imp in worst_improved if imp < 0
                ]
            },
            "chapter_comparisons": chapter_comparisons,
            "key_findings": self._generate_key_findings(
                improvement, best_improved, worst_improved, chapter_comparisons
            ),
            "recommendations": self._generate_recommendations(
                improvement, avg_dimension_improvements, chapter_comparisons
            ),
            "generated_at": datetime.now().isoformat()
        }
        
        # 保存报告
        report_path = self.reports_dir / "comparison_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # 生成文本报告
        text_report = self._generate_text_report(report)
        text_path = self.reports_dir / "comparison_report.txt"
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text_report)
        
        # 保存到数据库
        comparison = ComparisonReport(
            report_name=report["report_name"],
            novel_id=self.novel_id,
            overall_improvement=improvement_rate / 100,
            dimension_improvements=avg_dimension_improvements,
            key_improvements=[f"{dim}: +{imp:.2f}" for dim, imp in best_improved],
            persistent_issues=[f"{dim}: {imp:.2f}" for dim, imp in worst_improved if imp < 0],
            report_path=str(report_path),
            is_auto_generated=True
        )
        self.session.add(comparison)
        await self.session.commit()
        
        # 更新批次改进分数
        if self.batch_id:
            batch = await self.session.get(TrainingBatch, self.batch_id)
            if batch:
                batch.improvement_score = improvement
                batch.report_file_path = str(report_path)
                await self.session.commit()
        
        logger.info(f"[TrainingDataCollector] 对比报告生成完成: 改进率={improvement_rate:.1f}%")
        return report
    
    def _generate_key_findings(
        self,
        improvement: float,
        best_improved: List[Tuple[str, float]],
        worst_improved: List[Tuple[str, float]],
        chapter_comparisons: List[Dict]
    ) -> List[str]:
        """生成关键发现"""
        findings = []
        
        if improvement > 0:
            findings.append(f"训练带来正向改进，总分提升{improvement:.2f}分")
        elif improvement < 0:
            findings.append(f"训练后质量下降，总分降低{abs(improvement):.2f}分，需要检查训练过程")
        else:
            findings.append("训练前后质量无明显变化")
        
        if best_improved:
            findings.append(f"改进最明显的维度: {best_improved[0][0]} (+{best_improved[0][1]:.2f})")
        
        regressions = [dim for dim, imp in worst_improved if imp < 0]
        if regressions:
            findings.append(f"出现退步的维度: {', '.join(regressions)}")
        
        # 分析章节一致性
        improvements = [c["improvement"] for c in chapter_comparisons]
        if improvements:
            avg_imp = sum(improvements) / len(improvements)
            consistent = all(abs(imp - avg_imp) < 1.0 for imp in improvements)
            if consistent:
                findings.append("各章节改进程度较为一致")
            else:
                findings.append("各章节改进程度差异较大，建议针对性优化")
        
        return findings
    
    def _generate_recommendations(
        self,
        improvement: float,
        dimension_improvements: Dict[str, float],
        chapter_comparisons: List[Dict]
    ) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        if improvement < 0:
            recommendations.append("训练效果不理想，建议：1) 检查奖励函数设计 2) 增加训练数据 3) 调整学习率")
        elif improvement < 0.5:
            recommendations.append("改进幅度较小，建议增加训练轮次或调整策略网络")
        
        # 针对退步维度
        regressions = [(dim, imp) for dim, imp in dimension_improvements.items() if imp < 0]
        if regressions:
            dim_names = ", ".join([dim for dim, _ in regressions])
            recommendations.append(f"重点关注退步维度: {dim_names}")
        
        # 针对改进较小的维度
        small_improvements = [(dim, imp) for dim, imp in dimension_improvements.items() if 0 < imp < 0.3]
        if small_improvements:
            dim_names = ", ".join([dim for dim, _ in small_improvements])
            recommendations.append(f"以下维度改进有限，可考虑调整权重: {dim_names}")
        
        recommendations.append("建议定期执行基线评测，监控长期趋势")
        recommendations.append("可考虑引入人工反馈，校准自动评测")
        
        return recommendations
    
    def _generate_text_report(self, report: Dict[str, Any]) -> str:
        """生成文本格式报告"""
        lines = [
            "=" * 60,
            "KimiFiction RL训练对比报告",
            "=" * 60,
            "",
            f"批次名称: {report['batch_name']}",
            f"生成时间: {report['generated_at']}",
            "",
            "【总体改进】",
            f"  训练前平均分: {report['summary']['pre_training_score']:.2f}",
            f"  训练后平均分: {report['summary']['post_training_score']:.2f}",
            f"  绝对改进: {report['summary']['absolute_improvement']:+.2f}",
            f"  改进率: {report['summary']['improvement_rate']}",
            "",
            "【维度分析】",
        ]
        
        for dim, imp in report['dimension_analysis']['average_improvements'].items():
            lines.append(f"  {dim}: {imp:+.2f}")
        
        lines.extend([
            "",
            "【关键发现】",
        ])
        for finding in report['key_findings']:
            lines.append(f"  • {finding}")
        
        lines.extend([
            "",
            "【改进建议】",
        ])
        for rec in report['recommendations']:
            lines.append(f"  • {rec}")
        
        lines.extend([
            "",
            "【章节详情】",
        ])
        for comp in report['chapter_comparisons']:
            lines.append(f"  第{comp['chapter_number']}章: "
                        f"{comp['pre_score']:.2f} → {comp['post_score']:.2f} "
                        f"({comp['improvement']:+.2f})")
        
        lines.extend([
            "",
            "=" * 60,
            "报告结束",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def get_data_directory(self) -> str:
        """获取数据目录路径"""
        return str(self.batch_dir)
    
    async def export_training_data(
        self,
        format: str = "json"
    ) -> str:
        """
        导出训练数据
        
        Args:
            format: 导出格式 (json/csv)
            
        Returns:
            导出文件路径
        """
        result = await self.session.execute(
            select(TrainingEpisode).where(
                TrainingEpisode.novel_id == self.novel_id
            ).order_by(TrainingEpisode.episode_number)
        )
        episodes = result.scalars().all()
        
        export_data = []
        for ep in episodes:
            export_data.append({
                "episode_number": ep.episode_number,
                "chapter_number": ep.chapter_number,
                "round_number": ep.round_number,
                "action": ep.action_taken,
                "reward": ep.reward,
                "cumulative_reward": ep.cumulative_reward,
                "reader_score": ep.reader_score,
                "rubric_score": ep.rubric_score,
                "is_terminal": ep.is_terminal
            })
        
        if format == "json":
            export_path = self.batch_dir / "training_data_export.json"
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
        else:
            # CSV格式
            import csv
            export_path = self.batch_dir / "training_data_export.csv"
            with open(export_path, 'w', encoding='utf-8', newline='') as f:
                if export_data:
                    writer = csv.DictWriter(f, fieldnames=export_data[0].keys())
                    writer.writeheader()
                    writer.writerows(export_data)
        
        logger.info(f"[TrainingDataCollector] 导出训练数据: {len(export_data)}条记录 -> {export_path}")
        return str(export_path)
