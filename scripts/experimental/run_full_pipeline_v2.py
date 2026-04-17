#!/usr/bin/env python3
"""
第二轮完整训练流程：SFT v2 → GRPO v2

一键执行：
1. 增强版模仿学习数据生成（结构化上下文）
2. SFT/LoRA 微调
3. GRPO 强化学习优化
4. 生成完整报告

改进点汇总：
- 样本数：60 → 120
- 测试 Case：3 → 8
- SFT Epoch：1 → 2
- LoRA r：8 → 16
- max_length：512 → 768
- GRPO 迭代：6 → 10
- dialogue_score 权重：0.05 → 0.12
- 上下文结构：单一 prompt → 前文/细纲/角色/RAG/规则
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# 确保导入路径正确
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# 导入训练模块（动态导入，避免循环依赖）


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_full_pipeline_v2() -> Dict[str, Any]:
    """执行完整的第二轮训练流程"""
    start_time = datetime.now()
    
    print("=" * 60)
    print("KimiFiction 第二轮完整训练流程")
    print("=" * 60)
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 创建运行目录
    run_dir = ensure_dir(Path(__file__).parent / "training_runs" / f"full_v2_{start_time.strftime('%Y%m%d_%H%M%S')}")
    
    results = {
        "start_time": start_time.isoformat(),
        "run_dir": str(run_dir),
        "stages": {}
    }
    
    # ============================================
    # 阶段 1: SFT v2 训练
    # ============================================
    print("\n" + "=" * 60)
    print("阶段 1: SFT/LoRA v2 训练")
    print("=" * 60)
    
    try:
        from run_sft_v2 import run_training
        # 修改 run_sft_v2 的输出目录
        import run_sft_v2 as sft_module
        original_ensure_dir = sft_module.ensure_dir
        
        def patched_ensure_dir(path):
            # 将输出重定向到我们的运行目录
            if "sft_v2_" in str(path):
                new_path = run_dir / path.name
                return original_ensure_dir(new_path)
            return original_ensure_dir(path)
        
        sft_module.ensure_dir = patched_ensure_dir
        
        sft_result = run_training(run_dir)
        results["stages"]["sft"] = sft_result
        print(f"\n✅ SFT v2 完成:")
        print(f"   - Baseline 平均分: {sft_result.get('avg_baseline', 0):.4f}")
        print(f"   - SFT 平均分: {sft_result.get('avg_sft', 0):.4f}")
        print(f"   - 提升: {sft_result.get('improvement', 0):+.4f}")
        
    except Exception as e:
        print(f"\n❌ SFT v2 失败: {e}")
        traceback.print_exc()
        results["stages"]["sft"] = {"status": "failed", "error": str(e)}
        dump_json(run_dir / "PIPELINE_SUMMARY.json", results)
        return results
    
    # ============================================
    # 阶段 2: GRPO v2 训练
    # ============================================
    print("\n" + "=" * 60)
    print("阶段 2: GRPO v2 强化学习优化")
    print("=" * 60)
    
    try:
        grpo_result = run_grpo_v2()
        results["stages"]["grpo"] = grpo_result
        print(f"\n✅ GRPO v2 完成:")
        print(f"   - SFT 平均分: {grpo_result.get('avg_sft_score', 0):.4f}")
        print(f"   - GRPO 平均分: {grpo_result.get('avg_grpo_score', 0):.4f}")
        print(f"   - 提升: {grpo_result.get('improvement', 0):+.4f}")
        
    except Exception as e:
        print(f"\n❌ GRPO v2 失败: {e}")
        traceback.print_exc()
        results["stages"]["grpo"] = {"status": "failed", "error": str(e)}
        dump_json(run_dir / "PIPELINE_SUMMARY.json", results)
        return results
    
    # ============================================
    # 生成汇总报告
    # ============================================
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    results["end_time"] = end_time.isoformat()
    results["duration_seconds"] = round(duration, 2)
    
    # 计算总体提升
    baseline_avg = results["stages"]["sft"].get("avg_baseline", 0)
    final_avg = results["stages"]["grpo"].get("avg_grpo_score", 0)
    total_improvement = final_avg - baseline_avg
    
    results["summary"] = {
        "baseline_avg": round(baseline_avg, 4),
        "sft_avg": round(results["stages"]["sft"].get("avg_sft", 0), 4),
        "grpo_avg": round(final_avg, 4),
        "total_improvement": round(total_improvement, 4),
    }
    
    # 保存汇总
    dump_json(run_dir / "PIPELINE_SUMMARY.json", results)
    
    # 生成 Markdown 报告
    report_lines = [
        "# KimiFiction 第二轮完整训练报告",
        "",
        f"- 运行时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')} - {end_time.strftime('%H:%M:%S')}",
        f"- 总耗时: {duration:.1f} 秒",
        f"- 运行目录: `{run_dir}`",
        "",
        "---",
        "",
        "## 一、改进概览",
        "",
        "| 项目 | 第一轮 | 第二轮 | 改进 |",
        "|------|:------:|:------:|:----:|",
        "| 训练样本数 | 60 | 120 | +60 |",
        "| 测试 Case 数 | 3 | 8 | +5 |",
        "| SFT Epoch 数 | 1 | 2 | +1 |",
        "| LoRA r | 8 | 16 | +8 |",
        "| max_length | 512 | 768 | +256 |",
        "| GRPO 迭代次数 | 6 | 10 | +4 |",
        "| dialogue_score 权重 | 0.05 | 0.12 | +0.07 |",
        "| 上下文结构 | 单一 prompt | 前文/细纲/角色/RAG/规则 | 全面升级 |",
        "",
        "---",
        "",
        "## 二、训练结果汇总",
        "",
        "| 阶段 | 平均分 | vs Baseline | vs 上一阶段 |",
        "|------|:------:|:-----------:|:-----------:|",
        f"| Baseline | {baseline_avg:.4f} | - | - |",
        f"| SFT/LoRA v2 | {results['stages']['sft'].get('avg_sft', 0):.4f} | {results['stages']['sft'].get('improvement', 0):+.4f} | - |",
        f"| GRPO v2 | {final_avg:.4f} | {total_improvement:+.4f} | {results['stages']['grpo'].get('improvement', 0):+.4f} |",
        "",
        "---",
        "",
        "## 三、GRPO 策略收敛",
        "",
    ]
    
    policy = results["stages"]["grpo"].get("policy_summary", {})
    if policy:
        action_values = policy.get("action_values", {})
        report_lines.extend([
            "| 动作 | 最终价值 | 最终概率 |",
            "|------|:--------:|:--------:|",
            f"| generate | {action_values.get('generate', 0):.4f} | {policy.get('action_probs', {}).get('generate', 0):.4f} |",
            f"| revise | {action_values.get('revise', 0):.4f} | {policy.get('action_probs', {}).get('revise', 0):.4f} |",
            f"| delete | {action_values.get('delete', 0):.4f} | {policy.get('action_probs', {}).get('delete', 0):.4f} |",
            f"| keep | {action_values.get('keep', 0):.4f} | {policy.get('action_probs', {}).get('keep', 0):.4f} |",
            "",
        ])
    
    report_lines.extend([
        "---",
        "",
        "## 四、文件索引",
        "",
        "```",
        f"{run_dir}/",
        "├── 01_enhanced_imitation/",
        "│   ├── samples.json          # 120 条结构化训练样本",
        "│   └── statistics.json       # 样本统计",
        "├── 02_sft_lora_v2/",
        "│   ├── adapter/              # LoRA 适配器权重",
        "│   ├── training_metrics.json # SFT 训练指标",
        "│   ├── comparison.json       # 8 个 Case 对比",
        "│   └── report.md             # SFT 报告",
        "├── training_history.json     # GRPO 迭代历史",
        "├── comparison.json           # SFT vs GRPO 对比",
        "├── report.md                 # GRPO 报告",
        "└── PIPELINE_SUMMARY.json     # 本汇总",
        "```",
        "",
        "---",
        "",
        "## 五、下一步建议",
        "",
        "1. **数据质量**：检查 RAG 检索的相关段落是否真正有帮助",
        "2. **评估函数**：考虑引入真实 LLM 评估（Reader Agent）",
        "3. **更多场景**：扩展到 15+ 种场景类型",
        "4. **长文本**：支持 1000+ 字的完整章节生成",
        "5. **大纲遵循**：增加对预设大纲的遵循度评估",
    ])
    
    (run_dir / "FINAL_REPORT.md").write_text("\n".join(report_lines), encoding="utf-8")
    
    # 打印最终结果
    print("\n" + "=" * 60)
    print("训练完成!")
    print("=" * 60)
    print(f"总耗时: {duration:.1f} 秒")
    print(f"Baseline → 最终: {baseline_avg:.4f} → {final_avg:.4f} ({total_improvement:+.4f})")
    print(f"\n报告已保存到: {run_dir / 'FINAL_REPORT.md'}")
    print()
    
    return results


def main() -> None:
    try:
        result = run_full_pipeline_v2()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"训练流程失败: {e}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    main()
