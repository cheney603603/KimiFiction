#!/usr/bin/env python3
"""
训练演示脚本

演示完整的训练流程：
1. 模仿学习数据生成
2. LoRA微调
3. GRPO强化学习
4. 效果评估对比

运行后会生成详细的训练报告和对比结果。
"""
import asyncio
import sys
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.training.training_pipeline import TrainingPipeline


async def main():
    """主函数"""
    print("=" * 70)
    print("NovelGen 训练演示")
    print("=" * 70)
    print()
    
    # 创建Pipeline
    novel_id = 1
    project_path = "demo_training_output"
    
    print(f"项目ID: {novel_id}")
    print(f"输出目录: {project_path}")
    print()
    
    pipeline = TrainingPipeline(
        novel_id=novel_id,
        project_path=project_path,
        reference_dir="reference",
        base_model_path="models/Qwen3.5-2B-Q4_K_M.gguf",
    )
    
    # 运行完整Pipeline
    result = await pipeline.run_full_pipeline(
        run_imitation=True,
        run_lora=True,
        run_grpo=True,
        num_imitation_samples=50,  # 生成50个模仿学习样本
        lora_epochs=3,             # LoRA训练3轮
        grpo_iterations=10,        # GRPO训练10次迭代
    )
    
    # 打印结果摘要
    print()
    print("=" * 70)
    print("训练完成 - 结果摘要")
    print("=" * 70)
    print()
    
    print(f"Pipeline ID: {result.pipeline_id}")
    print(f"总耗时: {(result.end_time - result.start_time).total_seconds():.1f}秒")
    print()
    
    # 各阶段结果
    print("各阶段结果:")
    print("-" * 70)
    
    for i, stage in enumerate(result.stages, 1):
        status_icon = "✅" if stage.status == "success" else "⚠️" if stage.status == "skipped" else "❌"
        duration = (stage.end_time - stage.start_time).total_seconds()
        
        print(f"{status_icon} Stage {i}: {stage.stage_name}")
        print(f"   状态: {stage.status}")
        print(f"   耗时: {duration:.1f}秒")
        
        if stage.metrics:
            print(f"   指标:")
            for key, value in stage.metrics.items():
                print(f"      {key}: {value}")
        
        if stage.error_message:
            print(f"   错误: {stage.error_message}")
        
        print()
    
    # 对比结果
    print("=" * 70)
    print("效果对比")
    print("=" * 70)
    print()
    
    if result.comparison_results and "comparisons" in result.comparison_results:
        for i, comp in enumerate(result.comparison_results["comparisons"][:2], 1):
            print(f"测试用例 {i}: {comp['prompt'][:50]}...")
            print()
            
            for stage_name, output in comp["outputs"].items():
                print(f"  [{stage_name}] 评分: {output['score']:.2f}")
                print(f"  特点: {output['characteristics']}")
                print(f"  预览: {output['text'][:150]}...")
                print()
            
            print(f"  📈 提升: {comp['improvement']['grpo_vs_baseline']:.2%}")
            print()
            print("-" * 70)
            print()
    
    # 输出文件位置
    print("=" * 70)
    print("输出文件")
    print("=" * 70)
    print()
    print(f"训练输出目录: {project_path}/training_output/")
    print()
    print("重要文件:")
    print(f"  - 最终报告: {project_path}/training_output/FINAL_REPORT.json")
    print(f"  - 对比报告: {project_path}/training_output/04_evaluation/comparison_report.md")
    print(f"  - 模仿学习数据: {project_path}/training_output/01_imitation_learning/samples.json")
    print(f"  - LoRA配置: {project_path}/training_output/02_lora_finetune/config.json")
    print(f"  - GRPO结果: {project_path}/training_output/03_grpo_training/training_result.json")
    print()
    
    print("=" * 70)
    print("演示完成！")
    print("=" * 70)
    
    return result


if __name__ == "__main__":
    # 运行异步主函数
    result = asyncio.run(main())
    
    # 返回退出码
    all_success = all(s.status == "success" for s in result.stages)
    sys.exit(0 if all_success else 1)
