"""
测试脚本：验证角色API返回数据
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

# 添加backend目录到Python路径
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
sys.path.insert(0, backend_dir)

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.services.character_service import CharacterService
from loguru import logger


async def test_character_api_format():
    """测试角色API返回的数据格式"""
    
    novel_id = 1
    
    async with get_session() as db:
        char_service = CharacterService(db)
        
        # 获取角色列表
        characters = await char_service.list_characters(novel_id)
        
        logger.info("=" * 60)
        logger.info("测试角色API数据格式")
        logger.info("=" * 60)
        logger.info(f"找到 {len(characters)} 个角色\n")
        
        for char in characters:
            logger.info(f"角色: {char.name}")
            logger.info(f"  ID: {char.id}")
            logger.info(f"  Novel ID: {char.novel_id}")
            logger.info(f"  Role Type: {char.role_type.value}")
            logger.info(f"  Profile: {json.dumps(char.profile, ensure_ascii=False, indent=2)}")
            logger.info(f"  Current Status: {char.current_status}")
            logger.info(f"  Arc Progress: {char.arc_progress}")
            logger.info(f"  First Appearance: {char.first_appearance}")
            logger.info(f"  Created At: {char.created_at}")
            logger.info(f"  Updated At: {char.updated_at}")
            
            # 测试 to_dict 方法
            char_dict = char.to_dict()
            logger.info(f"\n  to_dict() 输出:")
            logger.info(json.dumps(char_dict, ensure_ascii=False, indent=2))
            logger.info("\n" + "-" * 60)
        
        logger.info("\n" + "=" * 60)
        logger.info("API数据格式验证完成")
        logger.info("=" * 60)
        
        # 模拟API响应格式
        response = {
            "items": [char.to_dict() for char in characters],
            "total": len(characters)
        }
        
        logger.info("\n模拟API响应:")
        logger.info(json.dumps(response, ensure_ascii=False, indent=2))
        
        return response


if __name__ == "__main__":
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    try:
        asyncio.run(test_character_api_format())
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        sys.exit(1)
