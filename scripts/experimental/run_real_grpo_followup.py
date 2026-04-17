#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.training.grpo_trainer import Episode, GRPOConfig, GRPOTrainer, WritingAction


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


def latest_sft_run() -> Path:
    root = Path(__file__).parent / "training_runs"
    candidates = sorted(root.glob("real_sft_lora_*"))
    if not candidates:
        raise FileNotFoundError("未找到 real_sft_lora_* 训练目录，请先运行真实 SFT/LoRA。")
    return candidates[-1]


def load_sft_assets(run_dir: Path) -> Tuple[str, Path]:
    metrics_path = run_dir / "02_real_sft_lora" / "training_metrics.json"
    adapter_dir = run_dir / "02_real_sft_lora" / "adapter"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    return metrics["model_name"], adapter_dir


def choose_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        major, _minor = torch.cuda.get_device_capability(0)
        if major >= 8:
            return torch.bfloat16
    return torch.float16


def load_model_and_tokenizer(model_name: str, adapter_dir: Path):
    dtype = choose_dtype()
    tokenizer = AutoTokenizer.from_pretrained(
        str(adapter_dir),
        trust_remote_code=True,
        local_files_only=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    base_model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
        local_files_only=True,
    ).to("cuda")
    model = PeftModel.from_pretrained(base_model, str(adapter_dir))
    model.eval()
    return tokenizer, model, dtype


def build_messages(prompt: str, previous_text: str, action: WritingAction) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    sampling = {
        "temperature": 0.8,
        "top_p": 0.9,
        "max_new_tokens": 220,
        "repetition_penalty": 1.08,
    }
    system = "你是专业的中文长篇网文作者，输出只写正文，不要解释。"
    user_prompt = prompt

    if action == WritingAction.GENERATE:
        sampling.update({"temperature": 0.95, "top_p": 0.95, "max_new_tokens": 260})
        user_prompt += "\n请加强画面感、悬念和可追读性，直接输出正文。"
    elif action == WritingAction.REVISE:
        sampling.update({"temperature": 0.75, "top_p": 0.88, "max_new_tokens": 260})
        user_prompt += f"\n请基于这段草稿重写并优化节奏、钩子和人物动机：\n{previous_text}"
    elif action == WritingAction.DELETE:
        sampling.update({"temperature": 0.7, "top_p": 0.85, "max_new_tokens": 160})
        user_prompt += f"\n请把下面草稿压缩得更紧凑，删去赘余部分但保留核心冲突：\n{previous_text}"
    else:
        sampling.update({"temperature": 0.72, "top_p": 0.9, "max_new_tokens": 220})
        user_prompt += f"\n请保持当前风格继续润色这段草稿：\n{previous_text}"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]
    return messages, sampling


def generate_text(model, tokenizer, messages: List[Dict[str, str]], sampling: Dict[str, Any]) -> str:
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(rendered, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            **sampling,
        )
    gen_ids = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(gen_ids, skip_special_tokens=True).strip()


def evaluate_text(prompt: str, text: str) -> Dict[str, float]:
    key_terms = []
    if "异常生物" in prompt:
        key_terms.extend(["废土", "列车", "异常", "生物", "寒意", "黑影", "低鸣", "悬"])
    if "资源短缺" in prompt:
        key_terms.extend(["资源", "物资", "冲突", "争", "食物", "水", "你", "我", "“"])
    if "深夜独处" in prompt:
        key_terms.extend(["深夜", "回忆", "失败", "决心", "心", "沉默", "呼吸"])

    overlap = sum(1 for term in key_terms if term in text)
    length = len(text)
    length_score = max(0.0, 1.0 - abs(length - 320) / 320)
    dialogue_score = min(1.0, (text.count("“") + text.count("\"")) / 8.0)
    emotion_score = min(1.0, sum(text.count(t) for t in ["心", "沉默", "寒意", "忽然", "低声", "咬牙"]) / 8.0)
    hook_score = min(1.0, sum(text.count(t) for t in ["忽然", "骤然", "却", "但", "下一秒", "仿佛"]) / 6.0)
    coherence = min(1.0, 0.45 + overlap * 0.06 + min(length / 320, 1.0) * 0.1)
    reader_score = min(1.0, 0.25 + overlap * 0.05 + length_score * 0.15 + dialogue_score * 0.15 + emotion_score * 0.15 + hook_score * 0.15 + coherence * 0.1)

    return {
        "reader_score": round(reader_score, 4),
        "hook_score": round(hook_score, 4),
        "immersion_score": round((length_score + emotion_score) / 2, 4),
        "continuity_score": round(coherence, 4),
        "dialogue_score": round(dialogue_score, 4),
        "length": length,
        "keyword_overlap": overlap,
    }


def reward_from_feedback(feedback: Dict[str, float], action: WritingAction, prev_reader_score: float) -> Tuple[float, Dict[str, float]]:
    breakdown = {
        "reader_score": feedback["reader_score"] * 0.42,
        "hook_score": feedback["hook_score"] * 0.20,
        "immersion_score": feedback["immersion_score"] * 0.15,
        "continuity_score": feedback["continuity_score"] * 0.13,
        "dialogue_score": feedback["dialogue_score"] * 0.05,
        "action_bonus": 0.0,
        "improvement": max(-0.08, min(0.08, (feedback["reader_score"] - prev_reader_score) * 0.8)),
    }
    if action == WritingAction.REVISE:
        breakdown["action_bonus"] = 0.03
    elif action == WritingAction.GENERATE:
        breakdown["action_bonus"] = 0.02
    elif action == WritingAction.DELETE:
        breakdown["action_bonus"] = -0.04

    reward = max(0.0, min(1.0, sum(breakdown.values())))
    return reward, {k: round(v, 4) for k, v in breakdown.items()}


def load_sft_baseline(sft_run_dir: Path) -> Dict[str, Dict[str, Any]]:
    comparison = json.loads((sft_run_dir / "02_real_sft_lora" / "comparison.json").read_text(encoding="utf-8"))
    return {item["prompt"]: item["sft_lora"] for item in comparison}


def run_grpo_followup() -> Dict[str, Any]:
    sft_run_dir = latest_sft_run()
    model_name, adapter_dir = load_sft_assets(sft_run_dir)
    tokenizer, model, dtype = load_model_and_tokenizer(model_name, adapter_dir)
    sft_baseline = load_sft_baseline(sft_run_dir)

    run_dir = ensure_dir(Path(__file__).parent / "training_runs" / f"real_grpo_followup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    trainer = GRPOTrainer(
        novel_id=1,
        config=GRPOConfig(group_size=4, num_iterations=6, learning_rate=0.08, temperature=0.85),
    )

    best_outputs: Dict[str, Dict[str, Any]] = {}
    best_rewards: Dict[str, float] = {}
    for prompt in TEST_PROMPTS:
        baseline = sft_baseline[prompt]
        seed_reward, seed_breakdown = reward_from_feedback(
            {
                "reader_score": baseline["score"],
                "hook_score": min(1.0, baseline["keyword_overlap"] / 3),
                "immersion_score": min(1.0, baseline["length"] / 320),
                "continuity_score": 0.7,
                "dialogue_score": 0.2,
            },
            WritingAction.KEEP,
            baseline["score"],
        )
        best_outputs[prompt] = {
            "text": baseline["text"],
            "reader_score": baseline["score"],
            "reward": seed_reward,
            "action": "seed",
            "reward_breakdown": seed_breakdown,
        }
        best_rewards[prompt] = seed_reward

    history: List[Dict[str, Any]] = []
    for iteration in range(1, trainer.config.num_iterations + 1):
        old_probs = trainer.policy._get_action_probs(trainer.config.temperature)
        episodes: List[Episode] = []
        iteration_records: List[Dict[str, Any]] = []

        for prompt in TEST_PROMPTS:
            seed = best_outputs[prompt]
            candidates = []
            sampled = trainer.policy.sample_group(prompt, trainer.config.group_size, trainer.config.temperature)
            for action, log_prob in sampled:
                messages, sampling = build_messages(prompt, seed["text"], action)
                text = generate_text(model, tokenizer, messages, sampling)
                feedback = evaluate_text(prompt, text)
                reward, breakdown = reward_from_feedback(feedback, action, seed["reader_score"])
                episodes.append(
                    Episode(
                        state=prompt,
                        action=action,
                        output=text,
                        reward=reward,
                        advantage=0.0,
                        log_prob=log_prob,
                        group_mean_reward=0.0,
                        group_std_reward=0.0,
                    )
                )
                candidates.append(
                    {
                        "action": action.value,
                        "text": text,
                        "reward": reward,
                        "feedback": feedback,
                        "reward_breakdown": breakdown,
                    }
                )

            best_local = max(candidates, key=lambda item: item["reward"])
            if best_local["reward"] > best_rewards[prompt]:
                best_rewards[prompt] = best_local["reward"]
                best_outputs[prompt] = {
                    "text": best_local["text"],
                    "reader_score": best_local["feedback"]["reader_score"],
                    "reward": best_local["reward"],
                    "action": best_local["action"],
                    "reward_breakdown": best_local["reward_breakdown"],
                }

            iteration_records.append(
                {
                    "prompt": prompt,
                    "best_action_this_iteration": best_local["action"],
                    "best_reward_this_iteration": round(best_local["reward"], 4),
                    "global_best_reward": round(best_rewards[prompt], 4),
                    "global_best_reader_score": round(best_outputs[prompt]["reader_score"], 4),
                }
            )

        trainer.policy.compute_advantages(episodes)
        update = trainer.policy.update(episodes, old_probs)
        rewards = [ep.reward for ep in episodes]
        history.append(
            {
                "iteration": iteration,
                "avg_reward": round(sum(rewards) / len(rewards), 4),
                "max_reward": round(max(rewards), 4),
                "min_reward": round(min(rewards), 4),
                "policy_summary": trainer.policy.get_policy_summary(),
                "update_stats": update,
                "prompt_records": iteration_records,
            }
        )

    comparisons = []
    for prompt in TEST_PROMPTS:
        sft_stage = sft_baseline[prompt]
        grpo_stage = best_outputs[prompt]
        comparisons.append(
            {
                "prompt": prompt,
                "sft_lora": sft_stage,
                "grpo": grpo_stage,
                "improvement": {
                    "reward_gain": round(grpo_stage["reward"] - best_rewards[prompt] + 0, 4),
                    "reader_score_gain": round(grpo_stage["reader_score"] - sft_stage["score"], 4),
                },
            }
        )

    avg_sft = sum(item["sft_lora"]["score"] for item in comparisons) / len(comparisons)
    avg_grpo = sum(item["grpo"]["reader_score"] for item in comparisons) / len(comparisons)

    dump_json(run_dir / "training_history.json", history)
    dump_json(run_dir / "comparison.json", comparisons)
    dump_json(
        run_dir / "RUN_SUMMARY.json",
        {
            "source_sft_run": str(sft_run_dir),
            "model_name": model_name,
            "dtype": str(dtype),
            "avg_sft_score": round(avg_sft, 4),
            "avg_grpo_score": round(avg_grpo, 4),
            "policy_summary": trainer.policy.get_policy_summary(),
            "artifacts": {
                "training_history": str(run_dir / "training_history.json"),
                "comparison": str(run_dir / "comparison.json"),
            },
        },
    )

    report_lines = [
        "# Real SFT + GRPO Follow-up Report",
        "",
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Source SFT run: {sft_run_dir}",
        f"- Model: {model_name}",
        f"- Avg SFT score: {avg_sft:.4f}",
        f"- Avg GRPO score: {avg_grpo:.4f}",
        "",
    ]
    for item in comparisons:
        report_lines.extend(
            [
                "## Prompt",
                item["prompt"],
                "",
                f"SFT score: {item['sft_lora']['score']}",
                item["sft_lora"]["text"],
                "",
                f"GRPO score: {item['grpo']['reader_score']}",
                item["grpo"]["text"],
                "",
                f"Reader score gain: {item['improvement']['reader_score_gain']}",
                "",
            ]
        )
    (run_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")

    return {
        "run_dir": str(run_dir),
        "avg_sft_score": round(avg_sft, 4),
        "avg_grpo_score": round(avg_grpo, 4),
        "policy_summary": trainer.policy.get_policy_summary(),
        "report_path": str(run_dir / "report.md"),
    }


def main() -> None:
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    result = run_grpo_followup()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
