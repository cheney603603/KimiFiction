#!/usr/bin/env python3
"""
第二轮完整训练流程：结构化上下文 + 更多测试 Case

改进点：
1. 使用 EnhancedImitationLearning 生成结构化上下文（前文/细纲/角色/RAG/规则）
2. 样本数从 60 增加到 120
3. 测试 Case 从 3 个增加到 8 个
4. SFT 训练参数优化（epoch 从 1 增加到 2，max_length 从 512 增加到 768）
5. dialogue_score 权重从 0.05 提升到 0.12
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import torch
from datasets import Dataset
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.training.enhanced_imitation import EnhancedImitationLearning


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


MODEL_CANDIDATES = [
    "Qwen/Qwen2.5-1.5B-Instruct",
]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_enhanced_samples(run_dir: Path, sample_count: int = 120) -> Tuple[List[Dict[str, Any]], Path]:
    """生成增强版训练样本"""
    imitation_dir = ensure_dir(run_dir / "01_enhanced_imitation")
    json_path = imitation_dir / "samples.json"
    
    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8")), json_path
    
    il = EnhancedImitationLearning(str(Path(__file__).parent / "reference"))
    il.build_index(chunk_size=500)
    il.generate_training_data(num_samples=sample_count, output_length=450)
    il.export_to_json(str(json_path))
    
    # 保存统计信息
    stats = il.get_statistics()
    dump_json(imitation_dir / "statistics.json", stats)
    
    return json.loads(json_path.read_text(encoding="utf-8")), json_path


def format_conversation(sample: Dict[str, Any], tokenizer) -> str:
    """格式化对话"""
    messages = [
        {"role": "system", "content": "你是专业的中文长篇网文作者，擅长根据上下文、细纲、角色设定和写作规则创作高质量小说章节。"},
        {"role": "user", "content": sample["prompt"]},
        {"role": "assistant", "content": sample["completion"]},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)


def build_dataset(samples: List[Dict[str, Any]], tokenizer, max_length: int = 768) -> Dataset:
    """构建数据集"""
    formatted = [{"text": format_conversation(sample, tokenizer)} for sample in samples]
    dataset = Dataset.from_list(formatted)

    def tokenize(batch):
        tokenized = tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_length,
            padding="max_length",
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    return dataset.map(tokenize, batched=True, remove_columns=["text"])


def choose_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        major, _minor = torch.cuda.get_device_capability(0)
        if major >= 8:
            return torch.bfloat16
    return torch.float16


def try_load_model(model_name: str, dtype: torch.dtype):
    # 设置离线模式
    os.environ["HF_HUB_OFFLINE"] = "1"
    
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
        local_files_only=True,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model.to("cuda")
    return tokenizer, model


def attach_lora(model):
    """LoRA 配置（优化版）"""
    config = LoraConfig(
        r=16,  # 从 8 增加到 16
        lora_alpha=32,  # 相应增加
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    peft_model = get_peft_model(model, config)
    peft_model.print_trainable_parameters()
    return peft_model, config


def generate_text(model, tokenizer, prompt: str, max_new_tokens: int = 300) -> str:
    """生成文本"""
    messages = [
        {"role": "system", "content": "你是专业的中文长篇网文作者，输出只写正文，不要解释。"},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.85,
            top_p=0.92,
            repetition_penalty=1.08,
            pad_token_id=tokenizer.pad_token_id,
        )
    gen_ids = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(gen_ids, skip_special_tokens=True).strip()


def evaluate_text_enhanced(prompt: str, text: str, requirements: List[str]) -> Dict[str, float]:
    """
    增强版评估函数
    
    改进：dialogue_score 权重从 0.05 提升到 0.12
    """
    # 基础指标
    length = len(text)
    keyword_overlap = sum(1 for term in ["废土", "列车", "异常", "生物", "资源", "冲突", 
                                          "深夜", "回忆", "决心", "末日", "战斗", "遗迹",
                                          "团队", "分歧", "独处", "感悟"] if term in prompt and term in text)
    
    # 长度评分
    length_score = max(0.0, 1.0 - abs(length - 350) / 350)
    
    # 对话评分（提升权重）
    dialogue_count = text.count("“") + text.count("\"")
    dialogue_score = min(1.0, dialogue_count / 6.0)
    
    # 情感评分
    emotion_keywords = ["心", "呼吸", "沉默", "低声", "忽然", "寒意", "颤抖", "坚定", "绝望", "希望"]
    emotion_score = min(1.0, sum(text.count(kw) for kw in emotion_keywords) / 10.0)
    
    # 悬念评分
    hook_keywords = ["忽然", "骤然", "却", "但", "下一秒", "就在这时", "突然", "猛地"]
    hook_score = min(1.0, sum(text.count(kw) for kw in hook_keywords) / 5.0)
    
    # 连贯性评分
    coherence_score = min(1.0, 0.5 + keyword_overlap * 0.1 + min(length / 350, 1.0) * 0.2)
    
    # 需求匹配评分
    requirement_score = 0.0
    for req in requirements:
        if req == "紧张感" and any(kw in text for kw in ["紧张", "紧绷", "心跳", "屏住"]):
            requirement_score += 0.2
        elif req == "悬念" and any(kw in text for kw in ["忽然", "就在这时", "猛地", "突然"]):
            requirement_score += 0.2
        elif req == "对白" and dialogue_count >= 4:
            requirement_score += 0.2
        elif req == "冲突" and any(kw in text for kw in ["争吵", "冲突", "分歧", "怒"]):
            requirement_score += 0.2
        elif req == "内心戏" and any(kw in text for kw in ["想起", "回忆", "闭上眼", "心中"]):
            requirement_score += 0.2
        elif req == "情感" and emotion_score > 0.3:
            requirement_score += 0.2
        elif req == "描写" and length > 250:
            requirement_score += 0.15
    requirement_score = min(1.0, requirement_score)
    
    # 综合评分（dialogue_score 权重提升）
    reader_score = (
        0.30 * keyword_overlap / max(len(requirements), 1) +
        0.20 * length_score +
        0.15 * dialogue_score +  # 提升权重
        0.12 * emotion_score +
        0.13 * hook_score +
        0.10 * coherence_score
    )
    reader_score = min(1.0, max(0.0, reader_score + requirement_score * 0.15))
    
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


def run_training(run_dir: Path) -> Dict[str, Any]:
    """运行完整训练流程"""
    
    # 1. 生成增强版训练样本
    samples, samples_path = prepare_enhanced_samples(run_dir, sample_count=120)
    sft_dir = ensure_dir(run_dir / "02_sft_lora_v2")
    dtype = choose_dtype()
    
    # 2. 加载模型
    load_errors: Dict[str, str] = {}
    tokenizer = None
    model = None
    model_name = None
    
    for candidate in MODEL_CANDIDATES:
        try:
            tokenizer, model = try_load_model(candidate, dtype)
            model_name = candidate
            break
        except RuntimeError as exc:
            load_errors[candidate] = f"RuntimeError: {exc}"
            torch.cuda.empty_cache()
        except Exception as exc:
            load_errors[candidate] = f"{type(exc).__name__}: {exc}"
            torch.cuda.empty_cache()
    
    if model is None or tokenizer is None or model_name is None:
        raise RuntimeError(f"无法加载任何候选模型: {json.dumps(load_errors, ensure_ascii=False)}")
    
    # 3. Baseline 评估
    baseline_outputs = {}
    for case in TEST_PROMPTS:
        text = generate_text(model, tokenizer, case["prompt"])
        baseline_outputs[case["id"]] = {
            "text": text,
            **evaluate_text_enhanced(case["prompt"], text, case["requirements"])
        }
    
    # 4. LoRA 微调
    peft_model, lora_config = attach_lora(model)
    tokenized_dataset = build_dataset(samples, tokenizer, max_length=768)
    
    training_args = TrainingArguments(
        output_dir=str(sft_dir / "trainer_output"),
        num_train_epochs=2,  # 从 1 增加到 2
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=10,
        save_strategy="epoch",
        fp16=(dtype == torch.float16),
        bf16=(dtype == torch.bfloat16),
        gradient_checkpointing=True,
        report_to="none",
        remove_unused_columns=False,
        warmup_ratio=0.1,  # 新增 warmup
    )
    
    trainer = Trainer(
        model=peft_model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    
    train_result = trainer.train()
    
    # 5. 保存 Adapter
    final_adapter_dir = ensure_dir(sft_dir / "adapter")
    trainer.save_model(str(final_adapter_dir))
    tokenizer.save_pretrained(str(final_adapter_dir))
    
    # 6. 微调后评估
    trained_model = PeftModel.from_pretrained(model, str(final_adapter_dir))
    trained_model.eval()
    
    finetuned_outputs = {}
    for case in TEST_PROMPTS:
        text = generate_text(trained_model, tokenizer, case["prompt"])
        finetuned_outputs[case["id"]] = {
            "text": text,
            **evaluate_text_enhanced(case["prompt"], text, case["requirements"])
        }
    
    # 7. 对比分析
    comparison = []
    for case in TEST_PROMPTS:
        baseline = baseline_outputs[case["id"]]
        finetuned = finetuned_outputs[case["id"]]
        
        comparison.append({
            "case_id": case["id"],
            "scene_type": case["scene_type"],
            "prompt": case["prompt"],
            "requirements": case["requirements"],
            "baseline": baseline,
            "sft_lora": finetuned,
            "improvement": {
                "reader_score": round(finetuned["reader_score"] - baseline["reader_score"], 4),
                "dialogue_score": round(finetuned["dialogue_score"] - baseline["dialogue_score"], 4),
                "hook_score": round(finetuned["hook_score"] - baseline["hook_score"], 4),
            }
        })
    
    # 8. 保存结果
    metrics = {
        "model_name": model_name,
        "dtype": str(dtype),
        "train_loss": train_result.metrics.get("train_loss"),
        "train_runtime": train_result.metrics.get("train_runtime"),
        "train_samples": len(samples),
        "epochs": 2,
        "max_length": 768,
        "lora_r": 16,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "load_errors": load_errors,
    }
    
    dump_json(sft_dir / "training_metrics.json", metrics)
    dump_json(sft_dir / "comparison.json", comparison)
    
    # 9. 生成报告
    avg_baseline = sum(c["baseline"]["reader_score"] for c in comparison) / len(comparison)
    avg_sft = sum(c["sft_lora"]["reader_score"] for c in comparison) / len(comparison)
    
    report_lines = [
        "# 第二轮 SFT/LoRA 训练报告（结构化上下文）",
        "",
        f"- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 模型: {model_name}",
        f"- 精度: {dtype}",
        f"- 训练样本: {len(samples)} (结构化上下文)",
        f"- Epochs: 2",
        f"- LoRA r: 16",
        f"- 训练耗时: {metrics['train_runtime']:.1f}s",
        f"- 训练 Loss: {metrics['train_loss']:.4f}",
        "",
        "## 总体结果",
        "",
        f"- Baseline 平均分: {avg_baseline:.4f}",
        f"- SFT/LoRA 平均分: {avg_sft:.4f}",
        f"- 平均提升: {avg_sft - avg_baseline:+.4f}",
        "",
        "## 各 Case 详情",
        "",
    ]
    
    for item in comparison:
        report_lines.extend([
            f"### {item['case_id']} - {item['scene_type']}",
            "",
            f"**Prompt**: {item['prompt']}",
            f"**需求**: {', '.join(item['requirements'])}",
            "",
            f"**Baseline ({item['baseline']['reader_score']:.4f})**:",
            item["baseline"]["text"][:300] + "...",
            "",
            f"**SFT/LoRA ({item['sft_lora']['reader_score']:.4f})**:",
            item["sft_lora"]["text"][:300] + "...",
            "",
            f"**提升**: reader_score {item['improvement']['reader_score']:+.4f}, "
            f"dialogue {item['improvement']['dialogue_score']:+.4f}",
            "",
        ])
    
    (sft_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    
    return {
        "run_dir": str(run_dir),
        "samples_path": str(samples_path),
        "metrics_path": str(sft_dir / "training_metrics.json"),
        "comparison_path": str(sft_dir / "comparison.json"),
        "report_path": str(sft_dir / "report.md"),
        "adapter_dir": str(final_adapter_dir),
        "metrics": metrics,
        "avg_baseline": round(avg_baseline, 4),
        "avg_sft": round(avg_sft, 4),
        "improvement": round(avg_sft - avg_baseline, 4),
    }


def main() -> None:
    run_dir = ensure_dir(Path(__file__).parent / "training_runs" / f"sft_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    try:
        result = run_training(run_dir)
        dump_json(run_dir / "RUN_SUMMARY.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        failure = {
            "status": "failed",
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "run_dir": str(run_dir),
        }
        dump_json(run_dir / "RUN_SUMMARY.json", failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        raise


if __name__ == "__main__":
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    main()
