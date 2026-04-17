#!/usr/bin/env python3
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

from app.training.imitation_learning import ImitationLearning


TEST_PROMPTS = [
    "写一段主角在废土列车外第一次发现异常生物的场景，要求有紧张感和悬念。",
    "描写主角与同伴在资源短缺时发生冲突，要求对白自然，人物立场鲜明。",
    "写一段主角深夜独处时回忆失败经历并重新下定决心的内心戏。",
]


MODEL_CANDIDATES = [
    "Qwen/Qwen2.5-1.5B-Instruct",
    "Qwen/Qwen2.5-0.5B-Instruct",
]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_imitation_samples(run_dir: Path, sample_count: int = 60) -> Tuple[List[Dict[str, Any]], Path]:
    imitation_dir = ensure_dir(run_dir / "01_imitation_learning")
    json_path = imitation_dir / "samples.json"
    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8")), json_path

    il = ImitationLearning(str(Path(__file__).parent / "reference"))
    il.load_references()
    il.analyze_styles()
    il.generate_training_samples(num_samples=sample_count, context_length=220, output_length=900)
    il.export_to_json(str(json_path))
    il.export_to_jsonl(str(imitation_dir / "samples.jsonl"))
    dump_json(imitation_dir / "style_summary.json", il.get_style_summary())
    (imitation_dir / "writing_guidelines.md").write_text(il.get_writing_guidelines(), encoding="utf-8")
    return json.loads(json_path.read_text(encoding="utf-8")), json_path


def format_conversation(sample: Dict[str, Any], tokenizer) -> str:
    messages = [
        {"role": "system", "content": "你是专业的中文长篇网文作者，擅长写高可读性的连载小说章节。"},
        {"role": "user", "content": sample["prompt"]},
        {"role": "assistant", "content": sample["completion"]},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)


def build_dataset(samples: List[Dict[str, Any]], tokenizer, max_length: int = 512) -> Dataset:
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
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model.to("cuda")
    return tokenizer, model


def attach_lora(model):
    config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    peft_model = get_peft_model(model, config)
    peft_model.print_trainable_parameters()
    return peft_model, config


def generate_text(model, tokenizer, prompt: str, max_new_tokens: int = 220) -> str:
    messages = [
        {"role": "system", "content": "你是专业的中文长篇网文作者，输出只写正文。"},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.8,
            top_p=0.9,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.pad_token_id,
        )
    gen_ids = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(gen_ids, skip_special_tokens=True).strip()


def evaluate_text(prompt: str, text: str) -> Dict[str, float]:
    prompt_terms = [term for term in ["废土", "列车", "异常", "生物", "资源", "冲突", "对白", "深夜", "回忆", "决心"] if term in prompt]
    overlap = sum(1 for term in prompt_terms if term in text)
    length = len(text)
    length_score = max(0.0, 1.0 - abs(length - 260) / 260)
    dialogue_bonus = min(0.2, (text.count("“") + text.count("\"")) * 0.04)
    emotional_bonus = min(0.2, sum(text.count(term) for term in ["心", "呼吸", "沉默", "低声", "忽然", "寒意"]) * 0.03)
    score = min(1.0, 0.35 + overlap * 0.12 + length_score * 0.18 + dialogue_bonus + emotional_bonus)
    return {"score": round(score, 4), "length": length, "keyword_overlap": overlap}


def run_training(run_dir: Path) -> Dict[str, Any]:
    samples, samples_path = prepare_imitation_samples(run_dir)
    sft_dir = ensure_dir(run_dir / "02_real_sft_lora")
    dtype = choose_dtype()

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

    baseline_outputs = {}
    for prompt in TEST_PROMPTS:
        text = generate_text(model, tokenizer, prompt)
        baseline_outputs[prompt] = {"text": text, **evaluate_text(prompt, text)}

    peft_model, lora_config = attach_lora(model)
    tokenized_dataset = build_dataset(samples, tokenizer, max_length=512)

    training_args = TrainingArguments(
        output_dir=str(sft_dir / "trainer_output"),
        num_train_epochs=1,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=5,
        save_strategy="epoch",
        fp16=(dtype == torch.float16),
        bf16=(dtype == torch.bfloat16),
        gradient_checkpointing=True,
        report_to="none",
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=peft_model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    train_result = trainer.train()
    final_adapter_dir = ensure_dir(sft_dir / "adapter")
    trainer.save_model(str(final_adapter_dir))
    tokenizer.save_pretrained(str(final_adapter_dir))

    trained_model = PeftModel.from_pretrained(model, str(final_adapter_dir))
    trained_model.eval()

    finetuned_outputs = {}
    for prompt in TEST_PROMPTS:
        text = generate_text(trained_model, tokenizer, prompt)
        finetuned_outputs[prompt] = {"text": text, **evaluate_text(prompt, text)}

    comparison = []
    for prompt in TEST_PROMPTS:
        comparison.append(
            {
                "prompt": prompt,
                "baseline": baseline_outputs[prompt],
                "sft_lora": finetuned_outputs[prompt],
                "improvement": round(finetuned_outputs[prompt]["score"] - baseline_outputs[prompt]["score"], 4),
            }
        )

    metrics = {
        "model_name": model_name,
        "dtype": str(dtype),
        "train_loss": train_result.metrics.get("train_loss"),
        "train_runtime": train_result.metrics.get("train_runtime"),
        "train_samples": len(samples),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "load_errors": load_errors,
    }

    dump_json(sft_dir / "training_metrics.json", metrics)
    dump_json(sft_dir / "comparison.json", comparison)

    report_lines = [
        "# Real SFT/LoRA Training Report",
        "",
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Model: {model_name}",
        f"- DType: {dtype}",
        f"- Train samples: {len(samples)}",
        f"- Train loss: {metrics['train_loss']}",
        f"- Train runtime: {metrics['train_runtime']}",
        "",
        "## Output Comparison",
        "",
    ]
    for item in comparison:
        report_lines.extend(
            [
                f"### Prompt",
                item["prompt"],
                "",
                f"Baseline score: {item['baseline']['score']}",
                item["baseline"]["text"],
                "",
                f"SFT/LoRA score: {item['sft_lora']['score']}",
                item["sft_lora"]["text"],
                "",
                f"Improvement: {item['improvement']}",
                "",
            ]
        )
    (sft_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")

    return {
        "run_dir": str(run_dir),
        "samples_path": str(samples_path),
        "metrics_path": str(sft_dir / "training_metrics.json"),
        "comparison_path": str(sft_dir / "comparison.json"),
        "report_path": str(sft_dir / "report.md"),
        "adapter_dir": str(final_adapter_dir),
        "metrics": metrics,
    }


def main() -> None:
    run_dir = ensure_dir(Path(__file__).parent / "training_runs" / f"real_sft_lora_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
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
