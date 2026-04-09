"""
RL训练与评测集成脚本
演示如何使用TrainingDataCollector和RubricEvaluationService

使用流程：
1. 初始化采集器
2. 执行训练前评测（建立基线）
3. 运行RL训练循环，采集每一轮数据
4. 执行训练后评测
5. 生成对比报告
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.training_data_collector import TrainingDataCollector
from app.services.rubric_evaluation_service import RubricEvaluationService
from app.writer_reader_rl import WriterReaderRL
from loguru import logger


async def demo_training_with_collection():
    """
    演示：带数据采集的RL训练
    
    场景：训练第1章，采集完整数据
    """
    novel_id = 999  # 测试小说ID
    project_path = r"D:\310Programm\KimiFiction\test_project"
    
    logger.info("=" * 60)
    logger.info("KimiFiction RL训练 + 数据采集演示")
    logger.info("=" * 60)
    
    # 步骤1: 初始化采集器
    async with TrainingDataCollector(
        novel_id=novel_id,
        project_path=project_path,
        batch_name="demo_batch_001"
    ) as collector:
        
        # 步骤2: 训练前评测（基线）
        logger.info("\n【步骤1】执行训练前评测...")
        pre_eval = await collector.evaluate_before_training([1])
        logger.info(f"训练前平均分: {pre_eval['average_score']:.2f}")
        
        # 步骤3: 运行RL训练循环（简化版）
        logger.info("\n【步骤2】运行RL训练循环...")
        
        # 模拟训练数据（实际应调用WriterReaderRL）
        for episode in range(1, 4):  # 模拟3个回合
            logger.info(f"  回合 {episode}/3...")
            
            # 模拟状态、动作、奖励
            state_draft = f"这是第{episode}版草稿..."
            action = "generate" if episode == 1 else "revise"
            action_probs = {"generate": 0.4, "revise": 0.4, "delete": 0.1, "keep": 0.1}
            reward = 0.5 + episode * 0.2  # 模拟奖励递增
            
            # 采集回合数据
            await collector.collect_episode(
                chapter_number=1,
                episode_number=episode,
                round_number=1,
                state_draft=state_draft,
                action_taken=action,
                action_probs=action_probs,
                reward=reward,
                reader_score=6.0 + episode,
                hook_score=7.0 + episode * 0.5,
                immersion_score=6.5 + episode * 0.5,
                policy_version=1,
                is_terminal=(episode == 3),
                termination_reason="达到目标分数" if episode == 3 else None
            )
        
        # 步骤4: 训练后评测
        logger.info("\n【步骤3】执行训练后评测...")
        post_eval = await collector.evaluate_after_training([1])
        logger.info(f"训练后平均分: {post_eval['average_score']:.2f}")
        
        # 步骤5: 生成对比报告
        logger.info("\n【步骤4】生成对比报告...")
        report = await collector.generate_comparison_report(pre_eval, post_eval)
        
        logger.info("\n" + "=" * 60)
        logger.info("训练完成！")
        logger.info(f"改进率: {report['summary']['improvement_rate']}")
        logger.info(f"数据目录: {collector.get_data_directory()}")
        logger.info("=" * 60)
        
        return report


async def demo_rubric_evaluation():
    """
    演示：Rubric结构化评测
    
    场景：评测单章质量
    """
    novel_id = 999
    
    logger.info("\n" + "=" * 60)
    logger.info("Rubric结构化评测演示")
    logger.info("=" * 60)
    
    # 初始化评测服务
    service = RubricEvaluationService(novel_id)
    await service.initialize(genre="玄幻")
    
    # 获取Rubric配置
    config = service.get_rubric_config()
    logger.info(f"\nRubric维度数: {len(config.get('dimensions', []))}")
    logger.info("维度列表:")
    for dim in config.get('dimensions', []):
        logger.info(f"  - {dim['name']}: 权重{dim['weight']:.2f}")
    
    # 模拟章节内容
    chapter_content = """
    第一章 测试章节
    
    这是一个测试用的章节内容，用于演示Rubric评测系统。
    系统将基于情节一致性、风格匹配度、逻辑合理性等维度进行评分。
    """
    
    # 执行评测
    logger.info("\n执行章节评测...")
    result = await service.evaluate_chapter(
        chapter_number=1,
        chapter_content=chapter_content,
        eval_type="baseline"
    )
    
    logger.info(f"\n评测结果:")
    logger.info(f"  总分: {result['total_score']:.2f}")
    logger.info(f"  加权分: {result['weighted_score']:.2f}")
    logger.info(f"  维度得分:")
    for dim, scores in result.get('dimension_scores', {}).items():
        logger.info(f"    - {dim}: {scores['score']:.1f}分 (权重{scores['weight']:.2f})")
    
    logger.info(f"\n总结反馈: {result['summary']}")
    logger.info("=" * 60)
    
    return result


async def demo_full_workflow():
    """
    演示：完整工作流程
    
    实际使用时的推荐流程
    """
    novel_id = 999
    project_path = r"D:\310Programm\KimiFiction\test_project"
    chapter_numbers = [1, 2, 3]  # 要训练的章节
    
    logger.info("\n" + "=" * 70)
    logger.info("KimiFiction 完整RL训练与评测流程")
    logger.info("=" * 70)
    
    async with TrainingDataCollector(
        novel_id=novel_id,
        project_path=project_path,
        batch_name="full_workflow_001"
    ) as collector:
        
        # Phase 1: 基线评测
        logger.info("\n【Phase 1】基线评测")
        logger.info("-" * 70)
        pre_eval = await collector.evaluate_before_training(chapter_numbers)
        
        # Phase 2: RL训练（简化演示）
        logger.info("\n【Phase 2】RL训练")
        logger.info("-" * 70)
        
        for chapter_num in chapter_numbers:
            logger.info(f"\n训练章节 {chapter_num}...")
            
            # 这里应该调用实际的WriterReaderRL
            # 为演示，模拟训练过程
            for round_num in range(1, 4):
                episode_data = {
                    "chapter_number": chapter_num,
                    "episode_number": (chapter_num - 1) * 3 + round_num,
                    "round_number": round_num,
                    "state_draft": f"章节{chapter_num}第{round_num}版",
                    "action_taken": ["generate", "revise", "keep"][round_num - 1],
                    "action_probs": {"generate": 0.3, "revise": 0.4, "keep": 0.2, "delete": 0.1},
                    "reward": 0.4 + round_num * 0.2,
                    "reader_score": 5.0 + round_num,
                    "hook_score": 6.0 + round_num * 0.5,
                    "immersion_score": 5.5 + round_num * 0.5,
                    "policy_version": 1,
                    "is_terminal": round_num == 3
                }
                
                await collector.collect_episode(**episode_data)
                logger.info(f"  回合 {round_num}/3 完成, reward={episode_data['reward']:.2f}")
        
        # Phase 3: 训练后评测
        logger.info("\n【Phase 3】训练后评测")
        logger.info("-" * 70)
        post_eval = await collector.evaluate_after_training(chapter_numbers)
        
        # Phase 4: 生成报告
        logger.info("\n【Phase 4】生成对比报告")
        logger.info("-" * 70)
        report = await collector.generate_comparison_report(pre_eval, post_eval)
        
        # Phase 5: 导出数据
        logger.info("\n【Phase 5】导出训练数据")
        logger.info("-" * 70)
        export_path = await collector.export_training_data(format="json")
        
        # 总结
        logger.info("\n" + "=" * 70)
        logger.info("流程完成！")
        logger.info("=" * 70)
        logger.info(f"训练章节数: {len(chapter_numbers)}")
        logger.info(f"训练前平均分: {pre_eval['average_score']:.2f}")
        logger.info(f"训练后平均分: {post_eval['average_score']:.2f}")
        logger.info(f"改进率: {report['summary']['improvement_rate']}")
        logger.info(f"数据目录: {collector.get_data_directory()}")
        logger.info(f"导出文件: {export_path}")
        logger.info("=" * 70)
        
        return {
            "pre_eval": pre_eval,
            "post_eval": post_eval,
            "report": report,
            "export_path": export_path
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="KimiFiction RL训练与评测演示")
    parser.add_argument(
        "--mode",
        choices=["training", "rubric", "full"],
        default="full",
        help="运行模式: training=仅训练采集, rubric=仅Rubric评测, full=完整流程"
    )
    
    args = parser.parse_args()
    
    if args.mode == "training":
        asyncio.run(demo_training_with_collection())
    elif args.mode == "rubric":
        asyncio.run(demo_rubric_evaluation())
    else:
        asyncio.run(demo_full_workflow())
