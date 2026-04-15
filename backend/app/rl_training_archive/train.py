"""
训练入口脚本

RL训练系统主入口
支持GRPO和TPO两种训练模式
"""
import asyncio
import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.rl_training.config import RLTrainingConfig
from app.rl_training.models import RLWritingModel
from app.rl_training.grpo_trainer import GRPOTrainer
from app.rl_training.tpo_trainer import TPOTrainer
from app.rl_training.data_pipeline import RLDataPipeline


async def main():
    """
    训练入口脚本
    
    使用方法：
    python -m app.rl_training.train --batch batch_001 --epochs 3 --mode grpo
    python -m app.rl_training.train --epochs 5 --mode tpo
    python -m app.rl_training.train --epochs 3 --mode both
    """
    parser = argparse.ArgumentParser(description="RL写作模型训练")
    parser.add_argument("--batch", default="latest", help="数据批次名称")
    parser.add_argument("--epochs", type=int, default=3, help="训练轮数")
    parser.add_argument(
        "--mode", 
        choices=["grpo", "tpo", "both"], 
        default="grpo",
        help="训练模式: grpo=GRPO训练, tpo=TPO优化, both=两者都执行"
    )
    parser.add_argument("--model", default=None, help="基础模型名称（覆盖配置）")
    parser.add_argument("--adapter", default=None, help="加载已有适配器路径")
    parser.add_argument("--lr", type=float, default=None, help="学习率")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("RL写作模型训练系统")
    print("=" * 60)
    print(f"模式: {args.mode}")
    print(f"批次: {args.batch}")
    print(f"轮数: {args.epochs}")
    
    # 1. 加载配置
    config = RLTrainingConfig()
    
    if args.model:
        config.model_name = args.model
    if args.lr:
        config.learning_rate = args.lr
        config.grpo_lr = args.lr
    
    print(f"\n配置:")
    print(f"  模型: {config.model_name}")
    print(f"  LoRA rank: {config.lora_rank}")
    print(f"  学习率: {config.learning_rate}")
    print(f"  批次大小: {config.batch_size} (累积: {config.gradient_accumulation})")
    
    # 2. 加载模型
    print("\n[1/4] 加载模型...")
    model = RLWritingModel(config)
    await model.load()
    
    if args.adapter:
        print(f"加载已有适配器: {args.adapter}")
        model.load_adapter(args.adapter)
    
    # 3. 加载数据
    print("\n[2/4] 加载数据...")
    pipeline = RLDataPipeline(config.data_dir)
    episodes = pipeline.load_episodes(args.batch)
    
    if not episodes:
        print("警告: 没有找到训练数据，创建合成数据用于测试...")
        episodes = pipeline.create_synthetic_episodes(num_episodes=10)
        pipeline.save_episodes(episodes, "synthetic_test")
    
    # 打印数据统计
    stats = pipeline.get_statistics(episodes)
    print(f"数据统计: {stats}")
    
    # 4. 执行训练
    print("\n[3/4] 开始训练...")
    
    if args.mode in ["grpo", "both"]:
        print("\n--- GRPO训练 ---")
        trainer = GRPOTrainer(model, config)
        history = await trainer.train(episodes, epochs=args.epochs)
        
        # 保存GRPO模型
        grpo_output = f"{config.output_dir}/grpo_adapter"
        model.save_adapter(grpo_output)
        print(f"GRPO模型已保存: {grpo_output}")
    
    if args.mode in ["tpo", "both"]:
        print("\n--- TPO优化 ---")
        tpo_trainer = TPOTrainer(model)
        
        # 使用第一个episode的prompt进行演示
        if episodes:
            test_prompt = episodes[0].prompt
            print(f"\n测试TPO优化，prompt: {test_prompt[:50]}...")
            
            optimized = await tpo_trainer.optimize(test_prompt, num_samples=4)
            print(f"优化结果:\n{optimized[:200]}...")
    
    # 5. 保存最终模型
    print("\n[4/4] 保存模型...")
    final_output = f"{config.output_dir}/final_adapter"
    model.save_adapter(final_output)
    
    print("\n" + "=" * 60)
    print("训练完成！")
    print(f"模型保存位置: {final_output}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
