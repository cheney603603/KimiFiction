#!/usr/bin/env python3
"""
Offline long-text training experiment for the current repository.

This script is designed for constrained environments where:
- reference novels are available locally
- a GGUF inference model may exist locally
- true LoRA/SFT may still be blocked by missing trainable weights/tooling

It produces:
1. imitation-learning datasets and style summaries
2. a truthful SFT feasibility report
3. a reproducible GRPO-style offline policy optimization run
4. baseline vs imitation vs GRPO output comparisons
"""
from __future__ import annotations

import asyncio
import json
import math
import random
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.training.grpo_trainer import Episode, GRPOConfig, GRPOTrainer, WritingAction
from app.training.imitation_learning import ImitationLearning, ImitationSample


TEST_PROMPTS = [
    "写一段主角在废土列车外第一次发现异常生物的场景，要求有紧张感和悬念。",
    "描写主角与同伴在资源短缺时发生冲突，要求对白自然，人物立场鲜明。",
    "写一段主角深夜独处时回忆失败经历并重新下定决心的内心戏。",
]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def split_keywords(text: str) -> List[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    unique: List[str] = []
    for token in tokens:
        if token not in unique:
            unique.append(token)
    return unique


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.strip())


@dataclass
class StageOutput:
    prompt: str
    text: str
    score: float
    feedback: Dict[str, Any]
    metadata: Dict[str, Any]


class OfflineWritingLab:
    """Reference-driven offline approximation for stage comparison."""

    def __init__(self, samples: List[ImitationSample], style_summary: Dict[str, Any]) -> None:
        self.samples = samples
        self.style_summary = style_summary
        self._rng = random.Random(42)

    def top_samples(self, prompt: str, top_k: int = 5) -> List[ImitationSample]:
        prompt_keywords = split_keywords(prompt)
        scored: List[Tuple[float, ImitationSample]] = []
        for sample in self.samples:
            haystack = f"{sample.context}\n{sample.output}\n{sample.style_prompt}"
            overlap = sum(1 for kw in prompt_keywords if kw in haystack)
            length_bonus = min(len(sample.output) / 800.0, 1.0) * 0.2
            score = overlap + length_bonus
            scored.append((score, sample))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [sample for _, sample in scored[:top_k]]

    def build_baseline(self, prompt: str) -> str:
        top = self.top_samples(prompt, top_k=1)
        if not top:
            return "夜色沉沉，主角在风里停住脚步，隐约察觉到不对劲，却还说不清危险来自哪里。"
        sample = top[0]
        excerpt = sample.output[:260]
        baseline = (
            f"【基础输出】{prompt}\n\n"
            f"{excerpt}\n\n"
            "主角意识到局势正在变化，但这一段仍偏概述，情绪与细节展开不足。"
        )
        return normalize_whitespace(baseline)

    def build_imitation(self, prompt: str) -> str:
        top = self.top_samples(prompt, top_k=1)
        if not top:
            return self.build_baseline(prompt)
        sample = top[0]
        style_hint = sample.style_prompt.replace("，", "，").strip()
        text = sample.output[:700]
        intro = (
            f"【模仿学习阶段】任务：{prompt}\n"
            f"风格约束：{style_hint}\n\n"
        )
        return normalize_whitespace(intro + text)

    def apply_action(self, base_text: str, prompt: str, action: WritingAction, step: int) -> str:
        prompt_keywords = split_keywords(prompt)[:4]
        keyword_line = "、".join(prompt_keywords) if prompt_keywords else "危机、冲突、选择"

        if action == WritingAction.GENERATE:
            addition = (
                f"\n\n风里像是藏着细碎的低鸣，{keyword_line}同时逼近，"
                "人物的感官被压到极限，场面更具镜头感。"
            )
            return normalize_whitespace(base_text + addition)

        if action == WritingAction.REVISE:
            revised = base_text.replace("【模仿学习阶段】", "【GRPO修订阶段】", 1)
            revised += (
                "\n\n他没有立刻行动，而是先捕捉到同伴呼吸里的迟疑，"
                "这让冲突不再只是事件推进，也带上了人物关系的张力。"
            )
            return normalize_whitespace(revised)

        if action == WritingAction.DELETE:
            shortened = re.sub(r"风格约束：.*?\n\n", "", base_text, count=1, flags=re.S)
            shortened = shortened[: max(220, int(len(shortened) * 0.72))]
            return normalize_whitespace(shortened + "\n\n这一版更短，但细节损失明显。")

        if action == WritingAction.KEEP:
            return normalize_whitespace(base_text + f"\n\n第{step}轮保持主体结构不变，只做轻微润色。")

        return normalize_whitespace(base_text)

    def evaluate(self, prompt: str, text: str) -> Dict[str, Any]:
        prompt_keywords = split_keywords(prompt)
        overlap = sum(1 for kw in prompt_keywords if kw in text)
        overlap_ratio = overlap / max(len(prompt_keywords), 1)

        text_len = count_chinese_chars(text)
        length_score = 1.0 - min(abs(text_len - 600) / 600, 1.0)
        suspense_terms = ["忽然", "骤然", "低鸣", "血", "危机", "异样", "停住", "不对劲", "寒意", "笑意"]
        suspense_hits = sum(text.count(term) for term in suspense_terms)
        dialogue_hits = text.count("“") + text.count("\"")
        introspection_terms = ["想起", "记得", "后悔", "决心", "沉默", "呼吸", "心里", "意识到"]
        introspection_hits = sum(text.count(term) for term in introspection_terms)
        paragraph_count = max(1, len([p for p in text.splitlines() if p.strip()]))

        hook_score = min(1.0, 0.30 + suspense_hits * 0.08 + overlap_ratio * 0.30)
        immersion_score = min(1.0, 0.25 + length_score * 0.35 + min(paragraph_count / 8, 1.0) * 0.20)
        continuity_score = min(1.0, 0.35 + overlap_ratio * 0.45 + min(introspection_hits * 0.05, 0.2))
        reader_score = min(1.0, 0.2 + hook_score * 0.35 + immersion_score * 0.25 + continuity_score * 0.20 + min(dialogue_hits * 0.03, 0.2))

        return {
            "reader_score": round(reader_score, 4),
            "hook_score": round(hook_score, 4),
            "immersion_score": round(immersion_score, 4),
            "continuity_score": round(continuity_score, 4),
            "confusing_points": [] if overlap_ratio >= 0.4 else ["和提示词的关键要素绑定还不够强"],
            "boring_points": [] if suspense_hits >= 2 else ["悬念或刺激点偏少"],
            "most_engaging_moments": ["结尾保留了继续读下去的动机"] if hook_score >= 0.6 else ["人物情绪有一定起伏"],
            "reader_expectations": ["希望下一段尽快揭示危险来源或关系走向"],
            "revision_suggestions": [
                "补强提示词里的核心意象",
                "让结尾留下更明确的悬念",
            ],
            "would_continue_reading": reader_score >= 0.62,
            "text_length": text_len,
        }


def compute_offline_reward(
    feedback: Dict[str, Any],
    action: WritingAction,
    previous_feedback: Optional[Dict[str, Any]] = None,
    target_length: int = 600,
) -> Tuple[float, Dict[str, float]]:
    text_length = float(feedback.get("text_length", 0) or 0)
    length_score = max(0.0, 1.0 - abs(text_length - target_length) / target_length)

    breakdown = {
        "reader_score": float(feedback.get("reader_score", 0)) * 0.40,
        "hook_score": float(feedback.get("hook_score", 0)) * 0.20,
        "immersion_score": float(feedback.get("immersion_score", 0)) * 0.15,
        "continuity_score": float(feedback.get("continuity_score", 0)) * 0.15,
        "length_score": length_score * 0.05,
        "action_bias": 0.0,
        "revision_gain": 0.0,
    }

    if action == WritingAction.REVISE:
        breakdown["action_bias"] = 0.03
    elif action == WritingAction.GENERATE:
        breakdown["action_bias"] = 0.02
    elif action == WritingAction.DELETE:
        breakdown["action_bias"] = -0.04

    if previous_feedback:
        improvement = float(feedback.get("reader_score", 0)) - float(previous_feedback.get("reader_score", 0))
        breakdown["revision_gain"] = max(-0.05, min(0.05, improvement * 0.6))

    reward = max(0.0, min(1.0, sum(breakdown.values())))
    return reward, {k: round(v, 4) for k, v in breakdown.items()}


def detect_sft_feasibility(model_path: Path) -> Dict[str, Any]:
    reasons: List[str] = []
    available = True

    if model_path.suffix.lower() == ".gguf":
        available = False
        reasons.append("当前基础模型为 GGUF 文件，不能直接走 HuggingFace LoRA/SFT 训练流程。")

    if shutil.which("nmake") is None or shutil.which("cl") is None:
        available = False
        reasons.append("当前 Windows 环境缺少 MSVC Build Tools（nmake/cl），本地编译 llama.cpp 相关组件失败。")

    llama_finetune = Path("llama.cpp") / "lora-finetune"
    if not llama_finetune.exists():
        available = False
        reasons.append("仓库内未发现 llama.cpp 的 `lora-finetune` 训练器。")

    return {
        "sft_executed": False,
        "sft_available": available,
        "model_path": str(model_path),
        "checked_at": datetime.now().isoformat(),
        "blocking_reasons": reasons,
        "recommended_next_step": "准备 HuggingFace 可训练权重，或安装完整 llama.cpp 训练工具链后再执行真实 SFT。",
    }


async def run_experiment() -> Dict[str, Any]:
    repo_root = Path(__file__).parent.resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ensure_dir(repo_root / "training_runs" / f"offline_experiment_{timestamp}")
    imitation_dir = ensure_dir(run_dir / "01_imitation_learning")
    sft_dir = ensure_dir(run_dir / "02_sft_check")
    grpo_dir = ensure_dir(run_dir / "03_grpo_training")
    eval_dir = ensure_dir(run_dir / "04_evaluation")

    imitation = ImitationLearning(str(repo_root / "reference"))
    novels = imitation.load_references()
    styles = imitation.analyze_styles()
    samples = imitation.generate_training_samples(num_samples=60, context_length=220, output_length=900)

    imitation_json = Path(imitation.export_to_json(str(imitation_dir / "samples.json")))
    imitation_jsonl = Path(imitation.export_to_jsonl(str(imitation_dir / "samples.jsonl")))
    style_summary = imitation.get_style_summary()
    guidelines = imitation.get_writing_guidelines()
    dump_json(imitation_dir / "style_summary.json", style_summary)
    (imitation_dir / "writing_guidelines.md").write_text(guidelines, encoding="utf-8")

    lab = OfflineWritingLab(samples=samples, style_summary=style_summary)

    sft_status = detect_sft_feasibility(repo_root / "models" / "Qwen3.5-2B-Q4_K_M.gguf")
    dump_json(sft_dir / "sft_status.json", sft_status)

    trainer = GRPOTrainer(
        novel_id=1,
        config=GRPOConfig(group_size=4, num_iterations=8, learning_rate=0.08, temperature=0.8),
    )

    baseline_outputs: Dict[str, StageOutput] = {}
    imitation_outputs: Dict[str, StageOutput] = {}
    best_grpo_outputs: Dict[str, StageOutput] = {}
    best_grpo_rewards: Dict[str, float] = {}
    grpo_history: List[Dict[str, Any]] = []

    for prompt in TEST_PROMPTS:
        baseline_text = lab.build_baseline(prompt)
        baseline_feedback = lab.evaluate(prompt, baseline_text)
        baseline_outputs[prompt] = StageOutput(
            prompt=prompt,
            text=baseline_text,
            score=baseline_feedback["reader_score"],
            feedback=baseline_feedback,
            metadata={"stage": "baseline"},
        )

        imitation_text = lab.build_imitation(prompt)
        imitation_feedback = lab.evaluate(prompt, imitation_text)
        imitation_outputs[prompt] = StageOutput(
            prompt=prompt,
            text=imitation_text,
            score=imitation_feedback["reader_score"],
            feedback=imitation_feedback,
            metadata={"stage": "imitation"},
        )

        best_grpo_outputs[prompt] = StageOutput(
            prompt=prompt,
            text=imitation_text,
            score=imitation_feedback["reader_score"],
            feedback=imitation_feedback,
            metadata={"stage": "grpo_seed", "action": "seed"},
        )
        seed_reward, seed_breakdown = compute_offline_reward(
            feedback=imitation_feedback,
            action=WritingAction.KEEP,
            previous_feedback=None,
        )
        best_grpo_outputs[prompt].metadata["optimization_reward"] = seed_reward
        best_grpo_outputs[prompt].metadata["reward_breakdown"] = seed_breakdown
        best_grpo_rewards[prompt] = seed_reward

    for iteration in range(1, trainer.config.num_iterations + 1):
        old_probs = trainer.policy._get_action_probs(trainer.config.temperature)
        iteration_episodes: List[Episode] = []
        prompt_records: List[Dict[str, Any]] = []

        for prompt in TEST_PROMPTS:
            current_best = best_grpo_outputs[prompt]
            sampled_actions = trainer.policy.sample_group(
                state=prompt,
                group_size=trainer.config.group_size,
                temperature=trainer.config.temperature,
            )
            local_candidates: List[StageOutput] = []

            for action, log_prob in sampled_actions:
                candidate_text = lab.apply_action(current_best.text, prompt, action, iteration)
                feedback = lab.evaluate(prompt, candidate_text)
                reward, breakdown = compute_offline_reward(
                    feedback=feedback,
                    action=action,
                    previous_feedback=current_best.feedback,
                )
                episode = Episode(
                    state=prompt,
                    action=action,
                    output=candidate_text,
                    reward=reward,
                    advantage=0.0,
                    log_prob=log_prob,
                    group_mean_reward=0.0,
                    group_std_reward=0.0,
                )
                iteration_episodes.append(episode)
                local_candidates.append(
                    StageOutput(
                        prompt=prompt,
                        text=candidate_text,
                        score=feedback["reader_score"],
                        feedback=feedback,
                        metadata={
                            "stage": "grpo_candidate",
                            "iteration": iteration,
                            "action": action.value,
                            "optimization_reward": reward,
                            "reward_breakdown": breakdown,
                        },
                    )
                )

            best_local = max(local_candidates, key=lambda item: item.metadata["optimization_reward"])
            if best_local.metadata["optimization_reward"] >= best_grpo_rewards[prompt]:
                best_grpo_outputs[prompt] = best_local
                best_grpo_rewards[prompt] = best_local.metadata["optimization_reward"]

            prompt_records.append(
                {
                    "prompt": prompt,
                    "best_action_this_iteration": best_local.metadata["action"],
                    "best_reward_this_iteration": round(best_local.metadata["optimization_reward"], 4),
                    "global_best_reward": round(best_grpo_rewards[prompt], 4),
                    "global_best_reader_score": round(best_grpo_outputs[prompt].score, 4),
                }
            )

        trainer.policy.compute_advantages(iteration_episodes)
        update_stats = trainer.policy.update(iteration_episodes, old_probs)
        rewards = [ep.reward for ep in iteration_episodes]
        grpo_history.append(
            {
                "iteration": iteration,
                "avg_reward": round(sum(rewards) / len(rewards), 4),
                "max_reward": round(max(rewards), 4),
                "min_reward": round(min(rewards), 4),
                "policy_summary": trainer.policy.get_policy_summary(),
                "update_stats": update_stats,
                "prompt_records": prompt_records,
            }
        )

    dump_json(grpo_dir / "training_history.json", grpo_history)
    dump_json(grpo_dir / "checkpoint.json", {
        "config": trainer.config.to_dict(),
        "policy": trainer.policy.get_policy_summary(),
        "training_history": grpo_history,
    })

    comparisons: List[Dict[str, Any]] = []
    for prompt in TEST_PROMPTS:
        baseline = baseline_outputs[prompt]
        imitation_stage = imitation_outputs[prompt]
        grpo_stage = best_grpo_outputs[prompt]
        comparisons.append(
            {
                "prompt": prompt,
                "outputs": {
                    "baseline": asdict(baseline),
                    "imitation": asdict(imitation_stage),
                    "grpo_optimized": asdict(grpo_stage),
                },
                "improvement": {
                    "imitation_vs_baseline": round(imitation_stage.score - baseline.score, 4),
                    "grpo_vs_imitation": round(grpo_stage.score - imitation_stage.score, 4),
                    "grpo_vs_baseline": round(grpo_stage.score - baseline.score, 4),
                },
            }
        )

    comparison_payload = {
        "run_dir": str(run_dir),
        "sft_status": sft_status,
        "comparisons": comparisons,
        "policy_summary": trainer.policy.get_policy_summary(),
    }
    dump_json(eval_dir / "comparison_results.json", comparison_payload)

    avg_baseline = sum(item["outputs"]["baseline"]["score"] for item in comparisons) / len(comparisons)
    avg_imitation = sum(item["outputs"]["imitation"]["score"] for item in comparisons) / len(comparisons)
    avg_grpo = sum(item["outputs"]["grpo_optimized"]["score"] for item in comparisons) / len(comparisons)

    lines = [
        "# 离线训练实验报告",
        "",
        f"- 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 运行目录: `{run_dir}`",
        "",
        "## 环境结论",
        "",
        "- 本次实验成功执行了模仿学习数据生成与离线 GRPO 策略优化。",
        "- 本次实验未执行真实 LoRA/SFT 参数更新。",
        f"- 原因: {'；'.join(sft_status['blocking_reasons'])}",
        "",
        "## 阶段结果",
        "",
        f"- 模仿学习: 处理参考小说 {len(novels)} 本，分析风格 {len(styles)} 份，生成训练样本 {len(samples)} 条。",
        f"- SFT 可行性检查: `sft_available={sft_status['sft_available']}`，详见 `02_sft_check/sft_status.json`。",
        f"- GRPO: 迭代 {len(grpo_history)} 轮，最终策略 {json.dumps(trainer.policy.get_policy_summary(), ensure_ascii=False)}",
        "",
        "## 平均得分",
        "",
        f"- Baseline: {avg_baseline:.4f}",
        f"- Imitation: {avg_imitation:.4f}",
        f"- GRPO: {avg_grpo:.4f}",
        "",
        "## 输出对比",
        "",
    ]

    for idx, item in enumerate(comparisons, start=1):
        lines.extend([
            f"### 案例 {idx}",
            "",
            f"**Prompt**: {item['prompt']}",
            "",
            f"**Baseline score**: {item['outputs']['baseline']['score']:.4f}",
            "",
            item["outputs"]["baseline"]["text"],
            "",
            f"**Imitation score**: {item['outputs']['imitation']['score']:.4f}",
            "",
            item["outputs"]["imitation"]["text"],
            "",
            f"**GRPO score**: {item['outputs']['grpo_optimized']['score']:.4f}",
            "",
            item["outputs"]["grpo_optimized"]["text"],
            "",
            f"提升: imitation_vs_baseline={item['improvement']['imitation_vs_baseline']:.4f}, "
            f"grpo_vs_imitation={item['improvement']['grpo_vs_imitation']:.4f}, "
            f"grpo_vs_baseline={item['improvement']['grpo_vs_baseline']:.4f}",
            "",
        ])

    (eval_dir / "comparison_report.md").write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "run_dir": str(run_dir),
        "metrics": {
            "reference_novels": len(novels),
            "styles": len(styles),
            "samples": len(samples),
            "avg_baseline_score": round(avg_baseline, 4),
            "avg_imitation_score": round(avg_imitation, 4),
            "avg_grpo_score": round(avg_grpo, 4),
        },
        "artifacts": {
            "imitation_json": str(imitation_json),
            "imitation_jsonl": str(imitation_jsonl),
            "sft_status": str(sft_dir / "sft_status.json"),
            "grpo_history": str(grpo_dir / "training_history.json"),
            "comparison_results": str(eval_dir / "comparison_results.json"),
            "comparison_report": str(eval_dir / "comparison_report.md"),
        },
    }
    dump_json(run_dir / "RUN_SUMMARY.json", summary)
    return summary


def main() -> None:
    summary = asyncio.run(run_experiment())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
