"""
TPO (Test-time Preference Optimization) 服务

在推理时进行偏好优化，提升生成质量。
核心思想：
1. 采样多个候选输出
2. 使用奖励模型评估每个候选
3. 选择最佳输出或进行加权组合
4. 可选：迭代优化

同时支持Test-Time Reinforcement Learning (Test-Time RL)
在推理时通过少量步骤的在线学习优化输出
"""
import json
import asyncio
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class CandidateOutput:
    """候选输出"""
    content: str
    score: float = 0.0
    feedback: Dict[str, Any] = field(default_factory=dict)
    generation_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TPOResult:
    """TPO优化结果"""
    final_output: str
    candidates: List[CandidateOutput]
    best_candidate_idx: int
    optimization_steps: int
    improvement: float  # 相比初始的最佳提升


class RewardModel:
    """
    奖励模型
    
    可以是：
    1. Reader Agent（基于规则）
    2. 训练过的神经网络模型
    3. 启发式评分函数
    """
    
    def __init__(self, reader_agent=None):
        self.reader_agent = reader_agent
        self.heuristic_weights = {
            "coherence": 0.25,
            "engagement": 0.25,
            "style": 0.20,
            "grammar": 0.15,
            "creativity": 0.15,
        }
    
    async def score(
        self,
        content: str,
        context: Dict[str, Any],
        outline: Optional[Dict] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """
        对输出进行评分
        
        Returns:
            (总分, 详细反馈)
        """
        scores = {}
        
        # 1. 使用Reader Agent评分
        if self.reader_agent:
            try:
                reader_context = {
                    "chapter_content": content,
                    "outline": outline or {},
                    "target_reader": context.get("target_reader", "大众网文读者"),
                }
                reader_result = await self.reader_agent.process(reader_context)
                reader_feedback = reader_result.get("reader_feedback", {})
                
                scores["reader_score"] = reader_feedback.get("reader_score", 0.5)
                scores["hook_score"] = reader_feedback.get("hook_score", 0.5)
                scores["immersion_score"] = reader_feedback.get("immersion_score", 0.5)
            except Exception as e:
                logger.warning(f"[RewardModel] Reader评分失败: {e}")
                scores["reader_score"] = 0.5
        
        # 2. 启发式评分
        heuristic_scores = self._heuristic_score(content)
        scores.update(heuristic_scores)
        
        # 计算加权总分
        total_score = (
            scores.get("reader_score", 0.5) * 0.4 +
            scores.get("hook_score", 0.5) * 0.2 +
            scores.get("coherence", 0.5) * 0.2 +
            scores.get("engagement", 0.5) * 0.2
        )
        
        return total_score, scores
    
    def _heuristic_score(self, content: str) -> Dict[str, float]:
        """启发式评分（不依赖外部模型）"""
        scores = {}
        
        # 连贯性：检查句子长度变化
        sentences = content.split('。')
        sentence_lengths = [len(s) for s in sentences if s.strip()]
        if sentence_lengths:
            avg_len = sum(sentence_lengths) / len(sentence_lengths)
            variance = sum((l - avg_len) ** 2 for l in sentence_lengths) / len(sentence_lengths)
            # 适度的变化表示连贯
            scores["coherence"] = 1.0 - min(variance / 1000, 0.5)
        else:
            scores["coherence"] = 0.5
        
        # 吸引力：检查对话比例和节奏
        dialogue_count = content.count('"') + content.count('"') + content.count("'") + content.count("'")
        dialogue_ratio = dialogue_count * 10 / max(len(content), 1)
        scores["engagement"] = 0.5 + min(dialogue_ratio, 0.3) - max(0, dialogue_ratio - 0.5)
        
        # 风格：检查词汇多样性
        words = content.split()
        unique_words = set(words)
        if words:
            diversity = len(unique_words) / len(words)
            scores["style"] = min(diversity * 3, 1.0)
        else:
            scores["style"] = 0.5
        
        # 语法：简单检查标点符号
        punctuation_ratio = sum(1 for c in content if c in '，。！？；：') / max(len(content), 1)
        scores["grammar"] = 1.0 - abs(punctuation_ratio - 0.15) * 5  # 期望约15%的标点
        scores["grammar"] = max(0.0, min(1.0, scores["grammar"]))
        
        return scores


class TPOService:
    """
    Test-time Preference Optimization服务
    
    在推理时优化生成结果
    """
    
    def __init__(
        self,
        reader_agent=None,
        num_candidates: int = 4,
        temperature_range: tuple = (0.5, 0.9),
    ):
        self.reward_model = RewardModel(reader_agent)
        self.num_candidates = num_candidates
        self.temperature_range = temperature_range
        
        logger.info(f"[TPOService] 初始化: num_candidates={num_candidates}")
    
    async def optimize(
        self,
        generate_fn: Callable,
        context: Dict[str, Any],
        outline: Optional[Dict] = None,
        num_candidates: Optional[int] = None,
    ) -> TPOResult:
        """
        执行TPO优化
        
        Args:
            generate_fn: 生成函数，接收context和temperature参数
            context: 生成上下文
            outline: 章节大纲
            num_candidates: 候选数量（覆盖默认值）
            
        Returns:
            优化结果
        """
        num_candidates = num_candidates or self.num_candidates
        
        logger.info(f"[TPOService] 开始TPO优化，生成{num_candidates}个候选")
        
        # 1. 生成多个候选
        candidates = await self._generate_candidates(
            generate_fn, context, num_candidates
        )
        
        # 2. 评估候选
        scored_candidates = await self._score_candidates(
            candidates, context, outline
        )
        
        # 3. 选择最佳候选
        best_idx, best_candidate = self._select_best(scored_candidates)
        
        # 4. 计算改进
        initial_best = max(c.score for c in scored_candidates[:1])
        improvement = best_candidate.score - initial_best
        
        result = TPOResult(
            final_output=best_candidate.content,
            candidates=scored_candidates,
            best_candidate_idx=best_idx,
            optimization_steps=1,
            improvement=improvement
        )
        
        logger.info(f"[TPOService] TPO完成: 最佳分数={best_candidate.score:.4f}, 改进={improvement:+.4f}")
        
        return result
    
    async def iterative_optimize(
        self,
        generate_fn: Callable,
        refine_fn: Callable,
        context: Dict[str, Any],
        outline: Optional[Dict] = None,
        num_iterations: int = 3,
    ) -> TPOResult:
        """
        迭代优化
        
        多轮生成-评估-改进
        
        Args:
            generate_fn: 初始生成函数
            refine_fn: 改进函数，接收content和feedback参数
            context: 生成上下文
            outline: 章节大纲
            num_iterations: 迭代次数
            
        Returns:
            优化结果
        """
        logger.info(f"[TPOService] 开始迭代优化，{num_iterations}轮")
        
        all_candidates = []
        
        # 初始生成
        current_content = await generate_fn(context, temperature=0.7)
        
        for iteration in range(num_iterations):
            # 评估当前内容
            score, feedback = await self.reward_model.score(
                current_content, context, outline
            )
            
            candidate = CandidateOutput(
                content=current_content,
                score=score,
                feedback=feedback,
                generation_params={"iteration": iteration}
            )
            all_candidates.append(candidate)
            
            logger.debug(f"[TPOService] 迭代{iteration}: 分数={score:.4f}")
            
            # 如果不是最后一轮，进行改进
            if iteration < num_iterations - 1:
                current_content = await refine_fn(current_content, feedback)
        
        # 选择最佳
        best_idx, best_candidate = self._select_best(all_candidates)
        
        # 计算改进
        initial_score = all_candidates[0].score if all_candidates else 0
        improvement = best_candidate.score - initial_score
        
        result = TPOResult(
            final_output=best_candidate.content,
            candidates=all_candidates,
            best_candidate_idx=best_idx,
            optimization_steps=num_iterations,
            improvement=improvement
        )
        
        logger.info(f"[TPOService] 迭代优化完成: 最佳分数={best_candidate.score:.4f}, 改进={improvement:+.4f}")
        
        return result
    
    async def _generate_candidates(
        self,
        generate_fn: Callable,
        context: Dict[str, Any],
        num_candidates: int
    ) -> List[str]:
        """生成多个候选输出"""
        candidates = []
        
        # 使用不同的temperature生成
        temp_step = (self.temperature_range[1] - self.temperature_range[0]) / max(num_candidates - 1, 1)
        
        for i in range(num_candidates):
            temperature = self.temperature_range[0] + temp_step * i
            
            try:
                content = await generate_fn(context, temperature=temperature)
                candidates.append(content)
                
                logger.debug(f"[TPOService] 候选{i+1}生成完成: temp={temperature:.2f}, 长度={len(content)}")
                
            except Exception as e:
                logger.error(f"[TPOService] 候选{i+1}生成失败: {e}")
                candidates.append("")
        
        return candidates
    
    async def _score_candidates(
        self,
        candidates: List[str],
        context: Dict[str, Any],
        outline: Optional[Dict]
    ) -> List[CandidateOutput]:
        """评估候选输出"""
        scored = []
        
        for content in candidates:
            if not content:
                scored.append(CandidateOutput(content="", score=0.0))
                continue
            
            try:
                score, feedback = await self.reward_model.score(content, context, outline)
                
                scored.append(CandidateOutput(
                    content=content,
                    score=score,
                    feedback=feedback
                ))
                
            except Exception as e:
                logger.error(f"[TPOService] 评分失败: {e}")
                scored.append(CandidateOutput(content=content, score=0.0))
        
        # 按分数排序
        scored.sort(key=lambda x: x.score, reverse=True)
        
        return scored
    
    def _select_best(self, candidates: List[CandidateOutput]) -> Tuple[int, CandidateOutput]:
        """选择最佳候选"""
        if not candidates:
            return -1, CandidateOutput(content="", score=0.0)
        
        best_idx = 0
        best_score = candidates[0].score
        
        for i, cand in enumerate(candidates[1:], 1):
            if cand.score > best_score:
                best_score = cand.score
                best_idx = i
        
        return best_idx, candidates[best_idx]
    
    def _combine_candidates(self, candidates: List[CandidateOutput]) -> str:
        """
        组合多个候选（高级功能）
        
        可以基于分数加权组合，或使用类似Best-of-N的策略
        """
        if not candidates:
            return ""
        
        # 简单实现：返回最佳候选
        # 可以扩展为：
        # 1. 基于分数的加权平均
        # 2. 使用另一个模型进行融合
        # 3. 提取各候选的优点组合
        
        best = max(candidates, key=lambda x: x.score)
        return best.content


class TestTimeRL:
    """
    Test-Time Reinforcement Learning
    
    在推理时进行少量步骤的在线强化学习
    """
    
    def __init__(
        self,
        reader_agent=None,
        num_steps: int = 5,
        learning_rate: float = 0.1,
    ):
        self.reward_model = RewardModel(reader_agent)
        self.num_steps = num_steps
        self.learning_rate = learning_rate
        
        logger.info(f"[TestTimeRL] 初始化: num_steps={num_steps}")
    
    async def optimize(
        self,
        initial_content: str,
        refine_fn: Callable[[str, Dict], str],
        context: Dict[str, Any],
        outline: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        执行Test-Time RL优化
        
        流程：
        1. 评估初始内容
        2. 生成改进方向
        3. 执行改进
        4. 重复直到收敛或达到最大步数
        
        Args:
            initial_content: 初始内容
            refine_fn: 改进函数
            context: 上下文
            outline: 大纲
            
        Returns:
            优化结果
        """
        current_content = initial_content
        history = []
        
        # 初始评估
        current_score, feedback = await self.reward_model.score(
            current_content, context, outline
        )
        
        history.append({
            "step": 0,
            "score": current_score,
            "feedback": feedback,
            "content_preview": current_content[:100] + "..."
        })
        
        logger.info(f"[TestTimeRL] 初始分数: {current_score:.4f}")
        
        for step in range(1, self.num_steps + 1):
            # 生成改进方向
            improvement_direction = self._generate_improvement_direction(feedback)
            
            # 执行改进
            try:
                new_content = await refine_fn(current_content, {
                    "direction": improvement_direction,
                    "feedback": feedback
                })
                
                # 评估新内容
                new_score, new_feedback = await self.reward_model.score(
                    new_content, context, outline
                )
                
                # 决定是否接受改进
                if new_score > current_score:
                    current_content = new_content
                    current_score = new_score
                    feedback = new_feedback
                    logger.debug(f"[TestTimeRL] 步骤{step}: 接受改进，新分数={new_score:.4f}")
                else:
                    logger.debug(f"[TestTimeRL] 步骤{step}: 拒绝改进，保持分数={current_score:.4f}")
                
                history.append({
                    "step": step,
                    "score": current_score,
                    "improvement": new_score - current_score,
                    "feedback": feedback,
                })
                
            except Exception as e:
                logger.error(f"[TestTimeRL] 步骤{step}失败: {e}")
                break
        
        final_improvement = history[-1]["score"] - history[0]["score"] if len(history) > 1 else 0
        
        result = {
            "final_content": current_content,
            "final_score": current_score,
            "initial_score": history[0]["score"],
            "improvement": final_improvement,
            "steps": len(history) - 1,
            "history": history,
        }
        
        logger.info(f"[TestTimeRL] 优化完成: 最终分数={current_score:.4f}, 改进={final_improvement:+.4f}")
        
        return result
    
    def _generate_improvement_direction(self, feedback: Dict[str, Any]) -> str:
        """基于反馈生成改进方向"""
        directions = []
        
        if feedback.get("reader_score", 0.5) < 0.6:
            directions.append("增强故事吸引力")
        
        if feedback.get("hook_score", 0.5) < 0.6:
            directions.append("强化开头和结尾的钩子")
        
        if feedback.get("coherence", 0.5) < 0.6:
            directions.append("提升段落连贯性")
        
        if feedback.get("engagement", 0.5) < 0.6:
            directions.append("增加对话和互动")
        
        if not directions:
            directions.append("全面提升写作质量")
        
        return "；".join(directions)


# 便捷函数
async def optimize_with_tpo(
    content: str,
    reader_agent,
    writer_agent,
    context: Dict[str, Any],
    outline: Optional[Dict] = None,
) -> str:
    """
    使用TPO优化内容的便捷函数
    
    Args:
        content: 初始内容
        reader_agent: Reader Agent
        writer_agent: Writer Agent
        context: 上下文
        outline: 大纲
        
    Returns:
        优化后的内容
    """
    tpo = TPOService(reader_agent, num_candidates=3)
    
    async def generate_fn(ctx, temperature):
        ctx["temperature"] = temperature
        result = await writer_agent.process(ctx)
        return result.get("content", "")
    
    result = await tpo.optimize(generate_fn, context, outline)
    return result.final_output


async def optimize_with_test_time_rl(
    content: str,
    reader_agent,
    writer_agent,
    context: Dict[str, Any],
    outline: Optional[Dict] = None,
) -> str:
    """
    使用Test-Time RL优化内容的便捷函数
    """
    ttrl = TestTimeRL(reader_agent, num_steps=3)
    
    async def refine_fn(content, feedback_info):
        # 构建改进提示
        ctx = context.copy()
        ctx["previous_draft"] = content
        ctx["reader_feedback"] = feedback_info.get("feedback", {})
        ctx["notes"] = feedback_info.get("direction", "改进质量")
        
        result = await writer_agent.process(ctx)
        return result.get("content", content)
    
    result = await ttrl.optimize(content, refine_fn, context, outline)
    return result["final_content"]
