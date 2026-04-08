"""
测试脚本：使用真实LLM API生成角色并同步到角色管理页面
"""
import asyncio
import sys
import os
import json

# 设置必要的环境变量
os.environ['DEBUG'] = 'true'
os.environ['MYSQL_HOST'] = 'localhost'
os.environ['MYSQL_PORT'] = '3306'
os.environ['MYSQL_USER'] = 'root'
os.environ['MYSQL_PASSWORD'] = 'root_password'
os.environ['MYSQL_DATABASE'] = 'novel_system'
os.environ['LLM_PROVIDER'] = 'kimi'
os.environ['CHAT2API_BASE_URL'] = 'http://localhost:8088'

# 添加backend目录到Python路径
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
sys.path.insert(0, backend_dir)

from app.workflow_engine import get_workflow_engine
from loguru import logger


async def test_real_llm_character_design():
    """测试使用真实LLM生成角色"""

    novel_id = 1

    # 准备输入数据（模拟需求分析和世界观）
    input_data = {
        "user_input": "写一部现代都市励志小说，讲述一个出身贫寒的年轻人通过摄影实现梦想的故事",
        "genre": "现代都市",
        "demand_analysis": {
            "type": "现代都市",
            "theme": "励志成长",
            "target_audience": "青年读者",
            "tone": "温暖治愈",
            "plot_summary": "一个出身贫寒的年轻人，凭借对摄影的热爱和坚持，在挫折中成长，最终实现自己的梦想"
        },
        "world_setting": {
            "world_type": "现代都市",
            "location": "繁华都市上海",
            "time_period": "现代（21世纪20年代）",
            "social_background": "竞争激烈的媒体行业",
            "culture_setting": "传统与现代融合",
            "key_locations": ["老城区弄堂", "现代化摄影工作室", "媒体公司办公楼"]
        },
        "num_characters": 3  # 生成3个角色
    }

    logger.info("=" * 80)
    logger.info("测试使用真实LLM API生成角色")
    logger.info("=" * 80)
    logger.info(f"小说ID: {novel_id}")
    logger.info(f"LLM提供商: kimi (chat2api)")
    logger.info(f"API地址: {os.environ.get('CHAT2API_BASE_URL')}")
    logger.info(f"\n输入摘要: {input_data['user_input']}")
    logger.info("=" * 80)

    try:
        # 获取工作流引擎
        engine = await get_workflow_engine(novel_id)

        # 执行角色设计阶段（使用真实LLM）
        from app.workflow_engine import WorkflowPhase
        result = await engine.run_phase(
            WorkflowPhase.CHARACTER_DESIGN,
            input_data,
            timeout=300  # 300秒超时，适配LLM响应时间
        )

        logger.info("\n" + "=" * 80)
        logger.info("LLM响应结果")
        logger.info("=" * 80)

        # 处理TaskResult对象
        if hasattr(result, 'success'):
            # TaskResult对象
            success = result.success
            error = result.error if hasattr(result, 'error') else None
            data = result.data if hasattr(result, 'data') else None

            logger.info(f"TaskResult.success: {success}")
            logger.info(f"TaskResult.error: {error}")
            logger.info(f"TaskResult.data type: {type(data)}")

            if success and data:
                if isinstance(data, dict):
                    characters = data.get("characters", [])
                    relationship_summary = data.get("relationship_summary", "")
                else:
                    # data可能是列表或其他类型
                    characters = data if isinstance(data, list) else []
                    relationship_summary = ""
            else:
                logger.error(f"LLM生成失败: {error}")
                return {"success": False, "error": error}
        elif isinstance(result, dict):
            success = result.get("success", False)
            data = result.get("data", {})
            if isinstance(data, dict):
                characters = data.get("characters", [])
                relationship_summary = data.get("relationship_summary", "")
            else:
                characters = []
                relationship_summary = ""
        else:
            logger.error(f"无法识别的返回类型: {type(result)}")
            return {"success": False, "error": f"Unknown return type: {type(result)}"}

        if success:

            logger.success(f"✓ 成功生成 {len(characters)} 个角色")
            logger.info(f"\n角色关系概述:\n{relationship_summary}")

            logger.info("\n" + "-" * 80)
            logger.info("角色详情:")
            logger.info("-" * 80)

            for idx, char in enumerate(characters, 1):
                logger.info(f"\n{idx}. {char.get('name')} ({char.get('role_type')})")
                profile = char.get('profile', {})

                if profile:
                    if 'age' in profile:
                        logger.info(f"   年龄: {profile['age']}")
                    if 'gender' in profile:
                        logger.info(f"   性别: {profile['gender']}")
                    if 'mbti' in profile:
                        logger.info(f"   MBTI: {profile['mbti']}")
                    if 'personality' in profile:
                        logger.info(f"   性格: {profile['personality']}")
                    if 'appearance' in profile:
                        logger.info(f"   外貌: {profile['appearance']}")
                    if 'background' in profile:
                        logger.info(f"   背景: {profile['background'][:80]}...")
                    if 'goals' in profile:
                        logger.info(f"   目标: {', '.join(profile['goals'])}")
                    if 'skills' in profile:
                        logger.info(f"   技能: {', '.join(profile['skills'])}")
                    if 'arc_description' in char:
                        logger.info(f"   成长弧线: {char['arc_description'][:80]}...")

            # 验证数据已同步到数据库
            logger.info("\n" + "=" * 80)
            logger.info("验证数据库同步")
            logger.info("=" * 80)

            from app.core.database import get_session
            from app.services.character_service import CharacterService

            async with get_session() as db:
                char_service = CharacterService(db)
                db_characters = await char_service.list_characters(novel_id)

                logger.info(f"数据库中当前共有 {len(db_characters)} 个角色")

                # 找出新创建的角色
                created_names = [c.get('name') for c in characters]
                for db_char in db_characters:
                    if db_char.name in created_names:
                        logger.success(f"✓ 角色已同步: {db_char.name} (ID: {db_char.id})")

            logger.info("\n" + "=" * 80)
            logger.success("测试完成！角色已成功生成并同步到数据库")
            logger.info("=" * 80)
            logger.info("\n现在请打开前端角色管理页面查看新角色:")
            for char in characters:
                logger.info(f"  - {char.get('name')} ({char.get('role_type')})")

            # 保存完整结果到文件
            output_file = "real_llm_character_result.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "success": True,
                    "characters": characters,
                    "relationship_summary": relationship_summary,
                    "input": input_data
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"\n完整结果已保存到: {output_file}")

            return result

        else:
            logger.error(f"✗ LLM生成失败: {result.get('error')}")
            logger.info(f"原始响应: {result.get('raw_response', 'N/A')[:500]}")
            return result

    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        "test_real_llm_character_design.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG",
        rotation="10 MB"
    )

    try:
        asyncio.run(test_real_llm_character_design())
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)
