#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from run_real_grpo_followup import latest_sft_run, run_grpo_followup
from run_real_sft_lora import run_training as run_real_sft_training


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_stage_report(sft_run_dir: Path, grpo_run_dir: Path, output_dir: Path) -> Dict[str, Any]:
    sft_comparison = load_json(sft_run_dir / "02_real_sft_lora" / "comparison.json")
    grpo_comparison = load_json(grpo_run_dir / "comparison.json")
    sft_metrics = load_json(sft_run_dir / "02_real_sft_lora" / "training_metrics.json")
    grpo_summary = load_json(grpo_run_dir / "RUN_SUMMARY.json")

    grpo_by_prompt = {item["prompt"]: item for item in grpo_comparison}
    merged_cases: List[Dict[str, Any]] = []
    for item in sft_comparison:
        prompt = item["prompt"]
        grpo_item = grpo_by_prompt[prompt]
        merged_cases.append(
            {
                "prompt": prompt,
                "baseline": item["baseline"],
                "sft_lora": item["sft_lora"],
                "grpo": grpo_item["grpo"],
                "improvement": {
                    "sft_vs_baseline": round(item["sft_lora"]["score"] - item["baseline"]["score"], 4),
                    "grpo_vs_sft": round(grpo_item["grpo"]["reader_score"] - item["sft_lora"]["score"], 4),
                    "grpo_vs_baseline": round(grpo_item["grpo"]["reader_score"] - item["baseline"]["score"], 4),
                },
            }
        )

    avg_baseline = sum(item["baseline"]["score"] for item in merged_cases) / len(merged_cases)
    avg_sft = sum(item["sft_lora"]["score"] for item in merged_cases) / len(merged_cases)
    avg_grpo = sum(item["grpo"]["reader_score"] for item in merged_cases) / len(merged_cases)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "sft_run_dir": str(sft_run_dir),
        "grpo_run_dir": str(grpo_run_dir),
        "model_name": sft_metrics["model_name"],
        "train_loss": sft_metrics["train_loss"],
        "train_runtime": sft_metrics["train_runtime"],
        "avg_scores": {
            "baseline": round(avg_baseline, 4),
            "sft_lora": round(avg_sft, 4),
            "grpo": round(avg_grpo, 4),
        },
        "policy_summary": grpo_summary["policy_summary"],
        "cases": merged_cases,
    }
    dump_json(output_dir / "FINAL_SUMMARY.json", summary)

    lines = [
        "# Real Training Pipeline Report",
        "",
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- SFT model: {sft_metrics['model_name']}",
        f"- SFT train loss: {sft_metrics['train_loss']}",
        f"- SFT train runtime: {sft_metrics['train_runtime']}",
        "",
        "## Average Scores",
        "",
        f"- Baseline: {avg_baseline:.4f}",
        f"- SFT/LoRA: {avg_sft:.4f}",
        f"- GRPO: {avg_grpo:.4f}",
        "",
    ]

    for idx, case in enumerate(merged_cases, start=1):
        lines.extend(
            [
                f"## Case {idx}",
                "",
                f"Prompt: {case['prompt']}",
                "",
                f"Baseline score: {case['baseline']['score']}",
                case["baseline"]["text"],
                "",
                f"SFT/LoRA score: {case['sft_lora']['score']}",
                case["sft_lora"]["text"],
                "",
                f"GRPO score: {case['grpo']['reader_score']}",
                case["grpo"]["text"],
                "",
                f"SFT vs baseline: {case['improvement']['sft_vs_baseline']}",
                f"GRPO vs SFT: {case['improvement']['grpo_vs_sft']}",
                f"GRPO vs baseline: {case['improvement']['grpo_vs_baseline']}",
                "",
            ]
        )

    (output_dir / "FINAL_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> None:
    root = Path(__file__).parent / "training_runs"
    pipeline_dir = ensure_dir(root / f"real_training_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    sft_run_dir = ensure_dir(pipeline_dir / "01_real_sft")
    run_real_sft_training(sft_run_dir)
    latest_sft = latest_sft_run()

    grpo_result = run_grpo_followup()
    grpo_run_dir = Path(grpo_result["run_dir"])

    summary = merge_stage_report(latest_sft, grpo_run_dir, pipeline_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
