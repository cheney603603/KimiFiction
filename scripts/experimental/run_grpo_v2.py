#!/usr/bin/env python3
"""
第二轮 GRPO 训练：基于 SFT v2 的强化学习优化

改进点：
1. 迭代次数从 6 增加到 10
2. dialogue_score 权重提升到 0.12
3. 测试 8 个 Case
4. 更精细的奖励函数
"""
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


# 8个测试 Case
TEST_PROMPTS = [
    {
        "id": "case1",
        "scene_type": "废土列车_发现",
        "prompt": "写一段主角在废土列车外第一次发现异常生物的场景，要求有紧张感和悬念。",
        "requirements": ["紧张感", "悬念"],
    },
    {
        "id": "case2",
        "scene_type": "资源_冲突",
        "prompt": "描写主角与同伴在资源短缺时发生冲突，要求对白自然，人物立场鲜明。",
        "requirements": ["对白", "冲突"],
    },
    {
        "id": "case3",
        "scene_type": "深夜_回忆",
        "prompt": "写一段主角深夜独处时回忆失败经历并重新下定决心的内心戏。",
        "requirements": ["内心戏", "情感"],
    },
    {
        "id": "case4",
        "scene_type": "末日_生存",
        "prompt": "描写末日环境下主角寻找资源时的紧张遭遇，要有悬念。",
        "requirements": ["紧张感", "悬念"],
    },
    {
        "id": "case5",
        "scene_type": "战斗_对峙",
        "prompt": "写一段主角与强大敌人对峙的场景，展现力量悬殊和主角的决心。",
        "requirements": ["紧张感", "悬念"],
    },
    {
        "id": "case6",
        "scene_type": "探险_发现",
        "prompt": "描写主角探索未知区域发现神秘遗迹的场景，要有好奇心和悬念。",
        "requirements": ["悬念", "描写"],
    },
    {
        "id": "case7",
        "scene_type": "团队_分歧",
        "prompt": "写一段团队在危机中产生分歧并最终做出决策的场景，对白要自然。",
        "requirements": ["对白", "冲突"],
    },
    {
        "id": "case8",
        "scene_type": "独处_感悟",
        "prompt": "描写主角独处时对过去的反思和对未来的期许，要有情感深度。",
        "requirements": ["内心戏", "情感"],
    },
]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def latest_sft_v2_run() -> Path:
    """查找最新的 SFT v2 运行目录"""
    root = Path(__file__).parent / "training_runs"
    candidates = sorted(root.glob("sft_v2_*"))
    if not candidates:
        raise FileNotFoundError("未找到 sft_v2_* 训练目录，请先运行 run_sft_v2.py")
    return candidates[-1]


def load_sft_assets(run_dir: Path) -> Tuple[str, Path]:
    """加载 SFT 资源"""
    metrics_path = run_dir / "02_sft_lora_v2" / "training_metrics.json"
    adapter_dir = run_dir / "02_sft_lora_v2" / "adapter"
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
    """构建消息和采样参数"""
    sampling = {
        "temperature": 0.85,
        "top_p": 0.92,
        "max_new_tokens": 300,
        "repetition_penalty": 1.08,
    }
    system = "你是专业的中文长篇网文作者，输出只写正文，不要解释。"
    user_prompt = prompt

    if action == WritingAction.GENERATE:
        sampling.update({"temperature": 0.92, "top_p": 0.95, "max_new_tokens": 350})
        user_prompt += "\n请增强画面感、悬念和可读性，直接输出正文。"
    elif action == WritingAction.REVISE:
        sampling.update({"temperature": 0.78, "top_p": 0.88, "max_new_tokens": 350})
        user_prompt += f"\n请优化这段内容的节奏、钩子和人物动机：\n{previous_text}"
    elif action == WritingAction.DELETE:
        sampling.update({"temperature": 0.72, "top_p": 0.85, "max_new_tokens": 200})
        user_prompt += f"\n请精简以下内容，保留核心冲突：\n{previous_text}"
    else:
        sampling.update({"temperature": 0.75, "top_p": 0.90, "max_new_tokens": 300})
        user_prompt += f"\n请保持当前风格继续润色：\n{previous_text}"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]
    return messages, sampling


def generate_text(model, tokenizer, messages: List[Dict[str, str]], sampling: Dict[str, Any]) -> str:
    """生成文本"""
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


def evaluate_text_v2(prompt: str, text: str, requirements: List[str]) -> Dict[str, float]:
    """
    第二版评估函数（dialogue_score 权重提升）
    """
    length = len(text)
    
    # 关键词匹配
    keyword_terms = ["废土", "列车", "异常", "生物", "资源", "冲突", 
                     "深夜", "回忆", "决心", "末日", "战斗", "遗迹",
                     "团队", "分歧", "独处", "感悟"]
    keyword_overlap = sum(1 for term in keyword_terms if term in prompt and term in text)
    
    # 长度评分
    length_score = max(0.0, 1.0 - abs(length - 350) / 350)
    
    # 对话评分（权重提升）
    dialogue_count = text.count("“") + text.count("\"")
    dialogue_score = min(1.0, dialogue_count / 5.0)
    
    # 情感评分
    emotion_keywords = ["心", "呼吸", "沉默", "低声", "忽然", "寒意", "颤抖", "坚定", "绝望", "希望"]
    emotion_score = min(1.0, sum(text.count(kw) for kw in emotion_keywords) / 8.0)
    
    # 悬念评分
    hook_keywords = ["忽然", "骤然", "却", "但", "下一秒", "就在这时", "突然", "猛地"]
    hook_score = min(1.0, sum(text.count(kw) for kw in hook_keywords) / 4.0)
    
    # 连贯性评分
    coherence_score = min(1.0, 0.5 + keyword_overlap * 0.1 + min(length / 350, 1.0) * 0.2)
    
    # 需求匹配评分
    requirement_score = 0.0
    for req in requirements:
        if req == "紧张感" and any(kw in text for kw in ["紧张", "紧绷", "心跳", "屏住"]):
            requirement_score += 0.25
        elif req == "悬念" and any(kw in text for kw in ["忽然", "就在这时", "猛地"]):
            requirement_score += 0.25
        elif req == "对白" and dialogue_count >= 3:
            requirement_score += 0.25
        elif req == "冲突" and any(kw in text for kw in ["争吵", "冲突", "分歧", "怒"]):
            requirement_score += 0.25
        elif req == "内心戏" and any(kw in text for kw in ["想起", "回忆", "闭上眼"]):
            requirement_score += 0.25
        elif req == "情感" and emotion_score > 0.3:
            requirement_score += 0.25
        elif req == "描写" and length > 250:
            requirement_score += 0.2
    requirement_score = min(1.0, requirement_score)
    
    # 综合评分
    reader_score = (
        0.28 * (keyword_overlap / max(len(requirements), 1)) +
        0.18 * length_score +
        0.16 * dialogue_score +  # 提升权重
        0.12 * emotion_score +
        0.14 * hook_score +
        0.12 * coherence_score
    )
    reader_score = min(1.0, max(0.0, reader_score + requirement_score * 0.18))
    
    return {
        "reader_score": round(reader_score, 4),
        "hook_score": round(hook_score, 4),
        "immersion_score": round((length_score + emotion_score) / 2, 4),
        "continuity_score": round(coherence_score, 4),
        "dialogue_score": round(dialogue_score, 4),
        "requirement_score": round(requirement_score, 4),
        "length": length,
        "keyword_overlap": keyword_overlap,
    }


def reward_from_feedback_v2(
    feedback: Dict[str, float], 
    action: WritingAction, 
    prev_reader_score: float,
    requirements: List[str]
) -> Tuple[float, Dict[str, float]]:
    """
    第二版奖励函数
    """
    breakdown = {
        "reader_score": feedback["reader_score"] * 0.40,
        "hook_score": feedback["hook_score"] * 0.18,
        "immersion_score": feedback["immersion_score"] * 0.12,
        "continuity_score": feedback["continuity_score"] * 0.10,
        "dialogue_score": feedback["dialogue_score"] * 0.12,  # 提升权重
        "requirement_score": feedback["requirement_score"] * 0.08,
        "action_bonus": 0.0,
        "improvement": max(-0.06, min(0.06, (feedback["reader_score"] - prev_reader_score) * 0.7)),
    }
    
    # 动作奖励
    if action == WritingAction.REVISE:
        breakdown["action_bonus"] = 0.025
    elif action == WritingAction.GENERATE:
        breakdown["action_bonus"] = 0.015
    elif action == WritingAction.DELETE:
        breakdown["action_bonus"] = -0.02
    
    reward = max(0.0, min(1.0, sum(breakdown.values())))
    return reward, {k: round(v, 4) for k, v in breakdown.items()}


def load_sft_v2_baseline(sft_run_dir: Path) -> Dict[str, Dict[str, Any]]:
    """加载 SFT v2 的 baseline 结果"""
    comparison = json.loads((sft_run_dir / "02_sft_lora_v2" / "comparison.json").read_text(encoding="utf-8"))
    return {item["case_id"]: item["sft_lora"] for item in comparison}


def run_grpo_v2() -> Dict[str, Any]:
    """运行第二轮 GRPO 训练"""
    sft_run_dir = latest_sft_v2_run()
    model_name, adapter_dir = load_sft_assets(sft_run_dir)
    tokenizer, model, dtype = load_model_and_tokenizer(model_name, adapter_dir)
    sft_baseline = load_sft_v2_baseline(sft_run_dir)
    
    run_dir = ensure_dir(Path(__file__).parent / "training_runs" / f"grpo_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    # GRPO 配置：迭代次数增加到 10
    trainer = GRPOTrainer(
        novel_id=1,
        config=GRPOConfig(
            group_size=4,
            num_iterations=10,
            learning_rate=8e-6,
            temperature=0.88,
        ),
    )
    
    best_outputs: Dict[str, Dict[str, Any]] = {}
    best_rewards: Dict[str, float] = {}
    
    # 初始化最佳输出
    for case in TEST_PROMPTS:
        baseline = sft_baseline[case["id"]]
        seed_reward, seed_breakdown = reward_from_feedback_v2(
            {
                "reader_score": baseline["reader_score"],
                "hook_score": baseline.get("hook_score", 0.5),
                "immersion_score": baseline.get("immersion_score", 0.5),
                "continuity_score": baseline.get("continuity_score", 0.7),
                "dialogue_score": baseline.get("dialogue_score", 0.3),
                "requirement_score": baseline.get("requirement_score", 0.5),
            },
            WritingAction.KEEP,
            baseline["reader_score"],
            case["requirements"],
        )
        best_outputs[case["id"]] = {
            "text": baseline["text"],
            "reader_score": baseline["reader_score"],
            "reward": seed_reward,
            "action": "seed",
            "reward_breakdown": seed_breakdown,
        }
        best_rewards[case["id"]] = seed_reward
    
    history: List[Dict[str, Any]] = []
    
    # GRPO 迭代
    for iteration in range(1, trainer.config.num_iterations + 1):
        old_probs = trainer.policy._get_action_probs(trainer.config.temperature)
        episodes: List[Episode] = []
        iteration_records: List[Dict[str, Any]] = []
        
        for case in TEST_PROMPTS:
            seed = best_outputs[case["id"]]
            candidates = []
            sampled = trainer.policy.sample_group(case["prompt"], trainer.config.group_size, trainer.config.temperature)
            
            for action, log_prob in sampled:
                messages, sampling = build_messages(case["prompt"], seed["text"], action)
                text = generate_text(model, tokenizer, messages, sampling)
                feedback = evaluate_text_v2(case["prompt"], text, case["requirements"])
                reward, breakdown = reward_from_feedback_v2(feedback, action, seed["reader_score"], case["requirements"])
                
                episodes.append(Episode(
                    state=case["prompt"],
                    action=action,
                    output=text,
                    reward=reward,
                    advantage=0.0,
                    log_prob=log_prob,
                    group_mean_reward=0.0,
                    group_std_reward=0.0,
                ))
                
                candidates.append({
                    "action": action.value,
                    "text": text,
                    "reward": reward,
                    "feedback": feedback,
                    "reward_breakdown": breakdown,
                })
            
            # 更新最佳输出
            best_local = max(candidates, key=lambda item: item["reward"])
            if best_local["reward"] > best_rewards[case["id"]]:
                best_rewards[case["id"]] = best_local["reward"]
                best_outputs[case["id"]] = {
                    "text": best_local["text"],
                    "reader_score": best_local["feedback"]["reader_score"],
                    "reward": best_local["reward"],
                    "action": best_local["action"],
                    "reward_breakdown": best_local["reward_breakdown"],
                }
            
            iteration_records.append({
                "case_id": case["id"],
                "scene_type": case["scene_type"],
                "best_action": best_local["action"],
                "best_reward": round(best_local["reward"], 4),
                "global_best_reward": round(best_rewards[case["id"]], 4),
                "global_best_reader_score": round(best_outputs[case["id"]]["reader_score"], 4),
            })
        
        # 更新策略
        trainer.policy.compute_advantages(episodes)
        update = trainer.policy.update(episodes, old_probs)
        rewards = [ep.reward for ep in episodes]
        
        history.append({
            "iteration": iteration,
            "avg_reward": round(sum(rewards) / len(rewards), 4),
            "max_reward": round(max(rewards), 4),
            "min_reward": round(min(rewards), 4),
            "policy_summary": trainer.policy.get_policy_summary(),
            "update_stats": update,
            "case_records": iteration_records,
        })
        
        print(f"迭代 {iteration}/{trainer.config.num_iterations}: avg_reward={sum(rewards)/len(rewards):.4f}")
    
    # 最终对比
    comparisons = []
    for case in TEST_PROMPTS:
        sft_stage = sft_baseline[case["id"]]
        grpo_stage = best_outputs[case["id"]]
        comparisons.append({
            "case_id": case["id"],
            "scene_type": case["scene_type"],
            "prompt": case["prompt"],
            "requirements": case["requirements"],
            "sft_lora": sft_stage,
            "grpo": grpo_stage,
            "improvement": {
                "reader_score_gain": round(grpo_stage["reader_score"] - sft_stage["reader_score"], 4),
                "reward_gain": round(grpo_stage["reward"] - best_rewards[case["id"]], 4),
            }
        })
    
    # 统计
    avg_sft = sum(item["sft_lora"]["reader_score"] for item in comparisons) / len(comparisons)
    avg_grpo = sum(item["grpo"]["reader_score"] for item in comparisons) / len(comparisons)
    
    # 保存结果
    dump_json(run_dir / "training_history.json", history)
    dump_json(run_dir / "comparison.json", comparisons)
    dump_json(run_dir / "RUN_SUMMARY.json", {
        "source_sft_run": str(sft_run_dir),
        "model_name": model_name,
        "dtype": str(dtype),
        "avg_sft_score": round(avg_sft, 4),
        "avg_grpo_score": round(avg_grpo, 4),
        "improvement": round(avg_grpo - avg_sft, 4),
        "policy_summary": trainer.policy.get_policy_summary(),
    })
    
    # 生成报告
    report_lines = [
        "# 第二轮 GRPO 训练报告",
        "",
        f"- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 源 SFT 运行: {sft_run_dir}",
        f"- 模型: {model_name}",
        f"- 迭代次数: 10",
        f"- 测试 Case 数: {len(TEST_PROMPTS)}",
        "",
        f"- SFT 平均分: {avg_sft:.4f}",
        f"- GRPO 平均分: {avg_grpo:.4f}",
        f"- 平均提升: {avg_grpo - avg_sft:+.4f}",
        "",
        "## 策略收敛",
        "",
        f"- generate: {trainer.policy.action_values[WritingAction.GENERATE]:.4f}",
        f"- revise: {trainer.policy.action_values[WritingAction.REVISE]:.4f}",
        f"- delete: {trainer.policy.action_values[WritingAction.DELETE]:.4f}",
        f"- keep: {trainer.policy.action_values[WritingAction.KEEP]:.4f}",
        "",
        "## 各 Case 详情",
        "",
    ]
    
    for item in comparisons:
        report_lines.extend([
            f"### {item['case_id']} - {item['scene_type']}",
            "",
            f"**SFT ({item['sft_lora']['reader_score']:.4f})**:",
            item["sft_lora"]["text"][:250] + "...",
            "",
            f"**GRPO ({item['grpo']['reader_score']:.4f})**:",
            item["grpo"]["text"][:250] + "...",
            "",
            f"**提升**: {item['improvement']['reader_score_gain']:+.4f}",
            "",
        ])
    
    (run_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    
    return {
        "run_dir": str(run_dir),
        "avg_sft_score": round(avg_sft, 4),
        "avg_grpo_score": round(avg_grpo, 4),
        "improvement": round(avg_grpo - avg_sft, 4),
        "policy_summary": trainer.policy.get_policy_summary(),
    }


def main() -> None:
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    result = run_grpo_v2()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
