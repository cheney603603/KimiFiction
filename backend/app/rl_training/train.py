"""
RL 训练入口脚本
=================

用法示例：
    python -m app.rl_training.train --novel-id 1 --epochs 3

推荐使用 app/training/training_pipeline.py 中的完整流程：
    from app.training import TrainingPipeline
"""

from app.training.grpo_trainer import GRPOTrainer, GRPOConfig
from app.training.lora_trainer import LoRATrainer, LoRAConfig
from app.training.training_pipeline import TrainingPipeline


def main():
    import argparse
    parser = argparse.ArgumentParser(description="KimiFiction RL 训练")
    parser.add_argument("--novel-id", type=int, required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--grpo", action="store_true", help="启用 GRPO 训练")
    parser.add_argument("--lora", action="store_true", help="启用 LoRA 微调")
    parser.add_argument("--pipeline", action="store_true", help="运行完整 Pipeline")
    args = parser.parse_args()

    if args.pipeline:
        import asyncio
        result = asyncio.run(
            TrainingPipeline(novel_id=args.novel_id, project_path="training_output")
            .run_full_pipeline(
                run_grpo=args.grpo,
                run_lora=args.lora,
                num_imitation_samples=50,
            )
        )
        print(f"Pipeline 完成: {result.pipeline_id}")
    else:
        print(f"[KimiFiction RL] 训练配置: novel_id={args.novel_id}, epochs={args.epochs}")
        print("提示：使用 --pipeline 运行完整训练流程")


if __name__ == "__main__":
    main()
