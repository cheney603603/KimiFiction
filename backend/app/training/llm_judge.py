"""
LLM-as-Judge 评估系统
======================

用 LLM 作为评判者（Judge），对小说生成质量进行多维度评分和成对比较。

设计理念：
1. **替代粗糙的规则评分** — 正则/启发式指标无法捕捉文学质量，LLM Judge 更可靠
2. **多维度 + CoT 推理** — 不是简单打分，而是要求 LLM 先分析再给分，降低随机性
3. **成对比较（Pairwise）** — "哪个更好"比"打几分"更稳定、区分度更高
4. **可配置 Judge 模型** — 支持不同能力的 LLM 作为 Judge（强模型 > 弱模型）
5. **与现有架构无缝集成** — 替换 ProgrammaticRubricEvaluator 的 LLM 分数部分，
   替换 GRPO RewardFunction 的固定映射 reward

参考论文:
- [Judging LLM-as-a-Judge] https://arxiv.org/abs/2306.05685
- [DeepSeek-R1] GRPO 的 reward model 设计
- [Prometheus] Fine-grained LLM Judge

使用方式:
    # 单次评分
    judge = LLMJudge()
    result = await judge.evaluate(content, outline, characters)

    # 成对比较
    comparison = await judge.compare(output_a, output_b, criteria="overall_quality")

    # 批量评估（用于 Stage 4 对比）
    batch_result = await judge.batch_evaluate(outputs_list, criteria)
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import json
import asyncio
from loguru import logger


# =============================================================================
# 评估维度定义
# =============================================================================

class JudgeDimension(str, Enum):
    """LLM Judge 评估维度"""
    PLOT_COHERENCE = "plot_coherence"           # 情节连贯性：因果链完整、伏笔回收
    CHARACTER_VOICE = "character_voice"         # 角色声音：对话符合人设、性格一致
    NARRATIVE_RHYTHM = "narrative_rhythm"       # 叙事节奏：张弛有度、不拖沓
    EMOTIONAL_RESONANCE = "emotional_resonance"  # 情感共鸣：读者代入感、感染力
    HOOK_RETENTION = "hook_retention"           # 追读钩子：悬念设置、吸引力
    STYLE_CONSISTENCY = "style_consistency"     # 风格一致：与参考风格/前文匹配
    LANGUAGE_QUALITY = "language_quality"       # 语言质量：文笔、描写、用词
    ORIGINALITY = "originality"                 # 原创性：不套路、有新意


# 各维度的中文标签和权重
DIMENSION_META: Dict[str, Dict[str, Any]] = {
    JudgeDimension.PLOT_COHERENCE.value: {
        "label": "情节连贯性",
        "weight": 0.18,
        "description": "因果关系是否成立、逻辑漏洞数量、伏笔回收",
    },
    JudgeDimension.CHARACTER_VOICE.value: {
        "label": "角色声音",
        "weight": 0.14,
        "description": "对话是否符合人设、角色行为是否前后一致、人物辨识度",
    },
    JudgeDimension.NARRATIVE_RHYTHM.value: {
        "label": "叙事节奏",
        "weight": 0.13,
        "description": "段落衔接自然度、张弛控制、信息密度合理性",
    },
    JudgeDimension.EMOTIONAL_RESONANCE.value: {
        "label": "情感共鸣",
        "weight": 0.15,
        "description": "读者代入感强度、情感描写的感染力、共情触发点",
    },
    JudgeDimension.HOOK_RETENTION.value: {
        "label": "追读钩子",
        "weight": 0.14,
        "description": "开篇吸引力、结尾悬念、读者继续阅读欲望",
    },
    JudgeDimension.STYLE_CONSISTENCY.value: {
        "label": "风格一致性",
        "weight": 0.10,
        "description": "与前文/目标风格的匹配度、语言基调统一性",
    },
    JudgeDimension.LANGUAGE_QUALITY.value: {
        "label": "语言质量",
        "weight": 0.10,
        "description": "文笔流畅度、描写生动性、用词精准度",
    },
    JudgeDimension.ORIGINALITY.value: {
        "label": "原创性",
        "weight": 0.06,
        "description": "是否有新意、避免套路化表达、创意亮点",
    },
}


# 评分量表定义（5级制 → 映射到1-10分）
RUBRIC_SCALE = """
## 评分标准（每维独立 1-10 分）

| 分数 | 等级 | 描述 |
|------|------|------|
| 9-10 | 优秀(S) | 该维度表现出色，无明显瑕疵，达到出版级水准 |
| 7-8 | 良好(A) | 整体良好，偶有小瑕疵但不影响阅读体验 |
| 5-6 | 合格(B) | 勉强合格，存在可改进之处，读者可能略感不适 |
| 3-4 | 不合格(C) | 明显缺陷，影响阅读体验，需要大幅修改 |
| 1-2 | 失败(D) | 完全不合格，该维度严重崩坏 |
"""


@dataclass
class DimensionScore:
    """单维度评分结果"""
    dimension: str
    score: float              # 1-10
    confidence: float         # 0-1, LLM对自己判断的确信度
    reasoning: str            # CoT 推理过程
    evidence_quotes: List[str] = field(default_factory=list)  # 引用的原文片段


@dataclass
class JudgeVerdict:
    """完整的 Judge 评判结果"""
    overall_score: float      # 加权总分 (0-1)
    dimension_scores: Dict[str, DimensionScore]
    strengths: List[str]      # 优势总结
    weaknesses: List[str]     # 劣势总结
    actionable_feedback: List[str]  # 可执行改进建议
    raw_response: str = ""    # 原始 LLM 响应
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """成对比较结果"""
    winner: str               # "A", "B", 或 "tie"
    confidence: float         # 比较确信度 (0-1)
    reason: str               # 判决理由
    dimension_comparison: Dict[str, Dict[str, float]]  # {dim: {"A": score, "B": score}}
    raw_response: str = ""


# =============================================================================
# Prompt 模板
# =============================================================================

# ── 单文本评分 Prompt（带 CoT 推理）──
EVALUATION_SYSTEM_PROMPT = """你是一位资深网络小说编辑兼文学评论家，拥有15年网文审稿经验。
你擅长从专业角度审视小说文本的质量，你的评分以严格但公正著称。

你的任务是对给定的小说片段进行多维度质量评估。

关键原则：
1. 先仔细阅读全文，形成整体印象
2. 逐维度分析时，必须引用原文作为证据
3. 评分要基于具体证据，而非模糊感觉
4. 给出分数后，要解释为什么不是更高/更低
5. 最后给出可执行的改进建议

输出必须是合法 JSON 格式。"""

EVALUATION_USER_TEMPLATE = """请对以下小说片段进行专业评估。

## 评估维度
{dimension_spec}

## 参考上下文
{context_section}

## 待评论文本
```
{text}
```

请输出JSON（包含所有8个维度的评分）：
```json
{{
  "dimensions": {{
    "plot_coherence": {{"score": <1-10>, "confidence": <0-1>, "reasoning": "<分析过程+证据>", "evidence": ["引用原文1"]}},
    "character_voice": {{"score": ..., "confidence": ..., "reasoning": "...", "evidence": [...]}}
    // ... 其余6个维度类似
  }},
  "strengths": ["优势1", "优势2"],
  "weaknesses": ["劣势1", "劣势2"],
  "actionable_feedback": ["具体建议1", "具体建议2"],
  "self_reflection": "如果让你改写这段文字，你最想改变什么？为什么？"
}}
```"""


# ── 成对比较 Prompt ──
COMPARISON_SYSTEM_PROMPT = """你是一位资深文学评委。你的专长是对比两段同题材文本的质量。

原则：
1. 不偏好长文本或短文本，只看质量
2. 关注实际阅读体验，而非理论标准
3. 如果两者差距不大，诚实地说出"难以抉择"
4. 必须给出具体的对比理由，不能只说"感觉更好"

输出合法 JSON。"""

COMPARISON_USER_TEMPLATE = """请对比以下两段小说文本的质量。

## 对比标准: {criteria_label}

### 文本 A
```
{text_a}
```

### 文本 B
```
{text_b}
```

## 共享上下文
{shared_context}

请输出JSON：
```json
{{
  "winner": "A" | "B" | "tie",
  "confidence": <0.0-1.0>,
  "reason": "详细说明选择理由，引用具体文本差异",
  "detailed_analysis": {{
    "plot_coherence": {{"A": <1-10>, "B": <1-10>, "comment": "对比评论"}},
    "character_voice": {{"A": <1-10>, "B": <1-10>, "comment": "..."}}
    // ... 关键维度对比
  }},
  "key_differences": [
    "文本A在XX方面做得更好，因为...",
    "文本B在XX方面存在问题..."
  ],
  "improvement_suggestions_for_loser": ["针对败者的改进建议"]
}}
```"""


# ── 快速筛选 Prompt（低延迟版）──
QUICK_SCREEN_PROMPT = """快速评估以下小说片段的整体质量（1-10分）。
只需要一个数字分数和一句话理由。

文本：
```
{text[:2000]}
```

输出格式：<分数> // <理由>"""


class LLMJudge:
    """
    LLM-as-Judge 评估器

    特性：
    - 多维度 CoT 评分（8 维 × 分析推理 + 证据引用）
    - 成对比较（Pairwise Comparison）
    - 快速筛选模式（低延迟，用于 GRPO 训练循环内）
    - 可配置的 Judge 能力等级
    """

    def __init__(
        self,
        llm_client=None,          # LLM 调用客户端（BaseAgent 或自定义）
        judge_level: str = "standard",  # "quick" / "standard" / "thorough"
        dimensions: Optional[List[JudgeDimension]] = None,
        temperature: float = 0.3,   # 低温度保证评分稳定性
        max_retries: int = 2,
    ):
        """
        Args:
            llm_client: 用于调用 LLM 的客户端（需支持 run_react_loop 或类似接口）
            judge_level: 评判深度 - quick(1次调用), standard(完整CoT), thorough(双pass验证)
            dimensions: 要评估的维度列表（默认全部8维）
            temperature: 采样温度（越低越稳定）
            max_retries: 解析失败时的重试次数
        """
        self.llm_client = llm_client
        self.judge_level = judge_level
        self.dimensions = dimensions or list(JudgeDimension)
        self.temperature = temperature
        self.max_retries = max_retries
        self._eval_count = 0

    async def evaluate(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        outline: Optional[Dict[str, Any]] = None,
        characters: Optional[List[Dict[str, Any]]] = None,
        reference_style: Optional[str] = None,
    ) -> JudgeVerdict:
        """
        对单个文本进行多维度 LLM Judge 评估

        Args:
            text: 待评估的小说文本
            context: 额外上下文（前文摘要等）
            outline: 当前章节大纲/细纲
            characters: 角色列表
            reference_style: 参考风格描述

        Returns:
            JudgeVerdict: 包含各维度分数、优劣势、建议
        """
        if not text or len(text.strip()) < 50:
            return self._empty_verdict("文本过短或为空")

        # 构造评估 prompt
        prompt = self._build_evaluation_prompt(
            text=text,
            context=context,
            outline=outline,
            characters=characters,
            reference_style=reference_style,
        )

        # 调用 LLM
        raw_response = await self._call_llm(prompt)

        if not raw_response:
            return self._empty_verdict("LLM 调用失败")

        # 解析结果
        verdict = self._parse_evaluation_response(raw_response, text)
        verdict.raw_response = raw_response
        verdict.metadata.update({
            "judge_level": self.judge_level,
            "text_length": len(text),
            "dimensions_evaluated": len(verdict.dimension_scores),
        })

        self._eval_count += 1
        return verdict

    async def compare(
        self,
        text_a: str,
        text_b: str,
        criteria: str = "overall_quality",
        shared_context: Optional[Dict[str, Any]] = None,
    ) -> ComparisonResult:
        """
        成对比较两个文本（比绝对评分更稳定）

        Args:
            text_a: 文本A
            text_b: 文本B
            criteria: 比较标准 ("overall_quality" / "hook_strength" / "emotional_impact")
            shared_context: 两段文本共享的上下文

        Returns:
            ComparisonResult: 比较结果（胜者 + 理由 + 分维对比）
        """
        criteria_labels = {
            "overall_quality": "综合质量",
            "hook_strength": "追读吸引力",
            "emotional_impact": "情感冲击力",
            "narrative_flow": "叙事流畅度",
            "style_match": "风格匹配度",
        }

        # 构造比较 prompt
        context_str = self._format_shared_context(shared_context) if shared_context else "无"

        prompt = COMPARISON_USER_TEMPLATE.format(
            criteria_label=criteria_labels.get(criteria, criteria),
            text_a=text_a[:4000],
            text_b=text_b[:4000],
            shared_context=context_str,
        )

        system_prompt = COMPARISON_SYSTEM_PROMPT

        # 调用 LLM
        raw_response = await self._call_llm(prompt, system_prompt=system_prompt)

        if not raw_response:
            return ComparisonResult(
                winner="tie",
                confidence=0.0,
                reason="LLM 调用失败，无法比较",
                dimension_comparison={},
                raw_response="",
            )

        # 解析比较结果
        result = self._parse_comparison_response(raw_response)
        result.raw_response = raw_response
        return result

    async def quick_score(self, text: str) -> Tuple[float, str]:
        """
        快速评分（用于 GRPO 训练循环内的实时 reward 计算）

        低延迟版本：单次 LLM 调用返回 (score, brief_reason)

        Returns:
            (score_1_10, reason_string)
        """
        if not text or len(text.strip()) < 20:
            return 3.0, "文本过短"

        prompt = QUICK_SCREEN_PROMPT.format(text=text)
        raw = await self._call_llm(prompt, temperature=0.2)

        if not raw:
            return 5.0, "评估超时/失败"

        # 提取分数
        numbers = re.findall(r'\b([1-9]|10)\b', raw.strip())
        if numbers:
            score = float(numbers[0])
            # 提取理由
            reason_match = re.search(r'//\s*(.+)', raw)
            reason = reason_match.group(1).strip() if reason_match else raw[:100]
            return score, reason

        return 5.0, f"解析失败: {raw[:50]}"

    async def batch_evaluate(
        self,
        texts: List[str],
        labels: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        parallel: bool = True,
    ) -> List[JudgeVerdict]:
        """
        批量评估多个文本（用于 Stage 4 跨阶段对比）

        Args:
            texts: 文本列表
            labels: 每个文本的标签（如 "baseline", "imitation", "lora", "grpo"）
            context: 共享上下文
            parallel: 是否并行执行

        Returns:
            评判结果列表
        """
        labels = labels or [f"text_{i}" for i in range(len(texts))]

        if parallel:
            tasks = [
                self.evaluate(
                    text=t,
                    context={**(context or {}), "source_label": label},
                )
                for t, label in zip(texts, labels)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # 将异常转为空 verdict
            final_results = []
            for r in results:
                if isinstance(r, Exception):
                    final_results.append(self._empty_verdict(str(r)))
                else:
                    final_results.append(r)
            return final_results
        else:
            results = []
            for t, label in zip(texts, labels):
                try:
                    v = await self.evaluate(text=t, context={**(context or {}), "source_label": label})
                    results.append(v)
                except Exception as e:
                    results.append(self._empty_verdict(str(e))
)
            return results

    async def compute_grpo_reward(
        self,
        output_text: str,
        action_name: str,
        previous_output: Optional[str] = None,
        outline: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        为 GRPO 训练计算奖励值

        这是 LLM Judge 与 GRPO 训练的核心集成点：
        用真实 LLM 评估替换原来的 action→fixed_reward 映射

        Args:
            output_text: Writer Agent 生成的输出
            action_name: 执行的动作名 (generate/revise/delete/keep)
            previous_output: 上一轮输出（用于计算改进幅度）
            outline: 大纲遵循检查

        Returns:
            (total_reward_0_1, breakdown_dict)
        """
        # 使用 quick_score 降低训练循环延迟
        base_score, reason = await self.quick_score(output_text)
        normalized_base = base_score / 10.0  # 归一化到 0-1

        breakdown = {
            "llm_judge_score": round(normalized_base, 3),
            "llm_judge_reason": reason[:100],
            "action_type": action_name,
        }

        # 改进幅度奖励（REVISE 动作专用）
        if action_name == "revise" and previous_output:
            prev_score, _ = await self.quick_score(previous_output)
            improvement = (base_score - prev_score) / 10.0
            improvement_bonus = max(-0.1, min(0.1, improvement * 0.5))
            breakdown["improvement_bonus"] = round(improvement_bonus, 3)
            normalized_base += improvement_bonus

        # 动作类型微调（保留合理的先验）
        action_adjustments = {
            "generate": 0.0,
            "revise": 0.02,    # 修改动作略微加分（鼓励迭代优化）
            "delete": -0.05,   # 删除动作略微扣分（除非内容确实差）
            "keep": -0.01,
        }
        adj = action_adjustments.get(action_name, 0.0)
        breakdown["action_adjustment"] = adj
        normalized_base += adj

        # 最终裁剪到 [0, 1]
        total_reward = max(0.0, min(1.0, normalized_base))
        breakdown["final_reward"] = round(total_reward, 4)

        return total_reward, breakdown

    # =========================================================================
    # 内部方法
    # =========================================================================

    def _build_evaluation_prompt(
        self,
        text: str,
        context: Optional[Dict[str, Any]],
        outline: Optional[Dict[str, Any]],
        characters: Optional[List[Dict[str, Any]]],
        reference_style: Optional[str],
    ) -> str:
        """构造完整评估 prompt"""
        # 维度规格说明
        dim_specs = []
        for dim in self.dimensions:
            meta = DIMENSION_META.get(dim.value, {})
            dim_specs.append(f"- **{meta.get('label', dim)}**: {meta.get('description', '')}")

        dimension_spec = "\n".join(dim_specs)

        # 上下文区域
        context_parts = []

        if outline:
            summary = outline.get("summary", "") or outline.get("title", "")
            context_parts.append(f"- 大纲摘要: {summary[:300]}")

        if characters:
            char_names = ", ".join(c.get("name", "?") for c in characters[:5])
            context_parts.append(f"- 涉及角色: {char_names}")

        if reference_style:
            context_parts.append(f"- 目标风格: {reference_style[:200]}")

        if context:
            prev_summary = context.get("previous_chapter_summary", "")
            if prev_summary:
                context_parts.append(f"- 前文摘要: {prev_summary[:300]}")

            scene_type = context.get("scene_type", "")
            if scene_type:
                context_parts.append(f"- 场景类型: {scene_type}")

        context_section = "\n".join(context_parts) if context_parts else "无额外上下文"

        # 截断过长文本（保留首尾）
        display_text = text
        if len(text) > 6000:
            display_text = text[:3000] + "\n\n... [中间部分省略] ...\n\n" + text[-2000:]

        return EVALUATION_USER_TEMPLATE.format(
            dimension_spec=dimension_spec,
            context_section=context_section,
            text=display_text,
        )

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """调用 LLM 并获取响应"""
        temp = temperature or self.temperature

        if self.llm_client is None:
            logger.warning("[LLMJudge] 未配置 LLM 客户端，返回空响应")
            return ""

        try:
            # 尝试通过 ReaderAgent/BaseAgent 的 run_react_loop 接口调用
            if hasattr(self.llm_client, 'run_react_loop'):
                react_result = await self.llm_client.run_react_loop(
                    prompt,
                    context={},
                    temperature=temp,
                    output_format="json",
                    system_prompt_override=system_prompt,
                )
                return react_result.get("final_text") or react_result.get("raw_response") or ""
            
            # 直接调用接口
            elif callable(self.llm_client):
                result = self.llm_client(prompt)
                if asyncio.iscoroutine(result):
                    result = await result
                return str(result) if result else ""

            else:
                logger.warning(f"[LLMJudge] 不支持的 client 类型: {type(self.llm_client)}")
                return ""

        except Exception as e:
            logger.error(f"[LLMJudge] LLM 调用异常: {e}")
            return ""

    def _parse_evaluation_response(self, raw: str, original_text: str) -> JudgeVerdict:
        """解析 LLM 评估响应"""
        parsed, extract_msg = self._extract_json_with_message(raw)
        if parsed is None:
            # 降级：尝试从文本中提取分数
            return self._fallback_parse(raw, original_text)

        # 构建维度分数
        dim_scores: Dict[str, DimensionScore] = {}
        dims_data = parsed.get("dimensions", {})

        for dim in self.dimensions:
            dim_key = dim.value if isinstance(dim, JudgeDimension) else dim
            dim_info = dims_data.get(dim_key, {})
            dim_scores[dim_key] = DimensionScore(
                dimension=dim_key,
                score=float(dim_info.get("score", 5.0)),
                confidence=float(dim_info.get("confidence", 0.7)),
                reasoning=str(dim_info.get("reasoning", ""))[:500],
                evidence_quotes=dim_info.get("evidence", [])[:3],
            )

        # 计算加权总分
        total = 0.0
        total_weight = 0.0
        for dim_key, ds in dim_scores.items():
            w = DIMENSION_META.get(dim_key, {}).get("weight", 0.1)
            total += ds.score * w
            total_weight += w
        overall = (total / total_weight / 10.0) if total_weight > 0 else 0.5

        return JudgeVerdict(
            overall_score=round(overall, 3),
            dimension_scores=dim_scores,
            strengths=parsed.get("strengths", []),
            weaknesses=parsed.get("weaknesses", []),
            actionable_feedback=parsed.get("actionable_feedback", []),
            metadata={"parse_method": "full_json"},
        )

    def _parse_comparison_response(self, raw: str) -> ComparisonResult:
        """解析比较结果"""
        parsed, _ = self._extract_json_with_message(raw)
        if parsed is None:
            return ComparisonResult(
                winner="tie",
                confidence=0.0,
                reason=f"解析失败: {raw[:100]}",
                dimension_comparison={},
            )

        winner = parsed.get("winner", "tie")
        if winner not in ("A", "B", "tie"):
            winner = "tie"

        dim_comp = {}
        detailed = parsed.get("detailed_analysis", {})
        for dim_key, values in detailed.items():
            if isinstance(values, dict):
                dim_comp[dim_key] = {
                    "A": float(values.get("A", 5.0)),
                    "B": float(values.get("B", 5.0)),
                }

        return ComparisonResult(
            winner=winner,
            confidence=float(parsed.get("confidence", 0.5)),
            reason=parsed.get("reason", "")[:500],
            dimension_comparison=dim_comp,
        )

    def _fallback_parse(self, raw: str, original_text: str) -> JudgeVerdict:
        """降级解析：当 JSON 失败时，从文本中尽力提取信息"""
        logger.info("[LLMJudge] 使用降级解析模式")

        dim_scores: Dict[str, DimensionScore] = {}

        # 尝试找 "X分" 或 "X/10" 模式
        score_pattern = r'(\d+(?:\.\d+)?)\s*[/／]?\s*10'
        all_scores = re.findall(score_pattern, raw)

        for i, dim in enumerate(self.dimensions):
            dim_key = dim.value if isinstance(dim, JudgeDimension) else dim
            if i < len(all_scores):
                dim_scores[dim_key] = DimensionScore(
                    dimension=dim_key,
                    score=float(all_scores[i]),
                    confidence=0.4,  # 低置信度（降级模式）
                    reasoning="(降级提取)",
                    evidence_quotes=[],
                )
            else:
                dim_scores[dim_key] = DimensionScore(
                    dimension=dim_key,
                    score=5.0,
                    confidence=0.1,
                    reasoning="(缺失)",
                    evidence_quotes=[],
                )

        # 尝试提取总体评价
        strengths = []
        weaknesses = []
        
        strength_match = re.search(r'(?:优势|优点|strength)[^:：]*[:：](.+)', raw)
        if strength_match:
            strengths = [s.strip() for s in strength_match.group(1).split('，')][:3]

        weakness_match = re.search(r'(?:劣势|缺点|不足|weakness)[^:：]*[:：](.+)', raw)
        if weakness_match:
            weaknesses = [w.strip() for w in weakness_match.group(1).split('，')][:3]

        return JudgeVerdict(
            overall_score=0.5,
            dimension_scores=dim_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            actionable_feedback=[],
            metadata={"parse_method": "fallback_regex"},
        )

    @staticmethod
    def _extract_json_with_message(response: str):
        """从响应中提取 JSON"""
        from app.core.json_utils import extract_json_from_response
        return extract_json_from_response(response)

    def _empty_verdict(self, reason: str) -> JudgeVerdict:
        """创建空评判结果"""
        dim_scores: Dict[str, DimensionScore] = {}
        for dim in self.dimensions:
            dim_key = dim.value if isinstance(dim, JudgeDimension) else dim
            dim_scores[dim_key] = DimensionScore(
                dimension=dim_key,
                score=0.0,
                confidence=0.0,
                reasoning=reason,
                evidence_quotes=[],
            )
        return JudgeVerdict(
            overall_score=0.0,
            dimension_scores=dim_scores,
            strengths=[],
            weaknesses=[f"评估失败: {reason}"],
            actionable_feedback=[],
            metadata={"error": reason},
        )

    @staticmethod
    def _format_shared_context(ctx: Dict[str, Any]) -> str:
        """格式化共享上下文"""
        parts = []
        if ctx.get("outline"):
            parts.append(f"大纲: {str(ctx['outline'])[:200]}")
        if ctx.get("scene_type"):
            parts.append(f"场景: {ctx['scene_type']}")
        if ctx.get("target_reader"):
            parts.append(f"目标读者: {ctx['target_reader']}")
        return "\n".join(parts) if parts else "无"


# =============================================================================
# 便捷函数
# =============================================================================

async def create_judge_with_agent(reader_agent=None) -> LLMJudge:
    """用现有的 ReaderAgent 创建 LLMJudge 实例"""
    return LLMJudge(
        llm_client=reader_agent,
        judge_level="standard",
    )


async def quick_evaluate_texts(
    texts: List[str],
    labels: Optional[List[str]] = None,
    reader_agent=None,
) -> Dict[str, Any]:
    """
    快速批量评估多个文本并生成排名报告

    用于 Stage 4 的跨阶段效果对比
    """
    judge = LLMJudge(llm_client=reader_agent, judge_level="standard")
    results = await judge.batch_evaluate(texts, labels=labels)

    # 排名
    ranked = sorted(
        [(r.overall_score, lbl) for r, lbl in zip(results, labels or [])],
        key=lambda x: x[0],
        reverse=True,
    )

    report = {
        "rankings": [{"rank": i + 1, "label": lbl, "score": sc} for i, (sc, lbl) in enumerate(ranked)],
        "details": [],
        "best": ranked[0][1] if ranked else None,
        "worst": ranked[-1][1] if ranked else None,
    }

    for r, lbl in zip(results, labels or []):
        detail = {
            "label": lbl,
            "overall_score": r.overall_score,
            "top_dimension": max(
                r.dimension_scores.items(),
                key=lambda x: x[1].score,
                default=(None, DimensionScore("", 0, 0, "", [])),
            )[0],
            "bottom_dimension": min(
                r.dimension_scores.items(),
                key=lambda x: x[1].score,
                default=(None, DimensionScore("", 10, 0, "", [])),
            )[0],
            "strengths": r.strengths[:2],
            "weaknesses": r.weaknesses[:2],
        }
        report["details"].append(detail)

    return report
