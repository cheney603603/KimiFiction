"""
测试脚本：通过API创建角色并验证同步到角色管理页面
"""
import asyncio
import sys
import os

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
from app.schemas.character import CharacterCreate
from loguru import logger


async def test_create_characters():
    """测试创建角色并验证同步"""
    
    # 获取一个novel_id（这里假设是1，实际可能需要先查询）
    novel_id = 1
    
    # 准备测试角色数据
    test_characters = [
        {
            "name": "李云",
            "role_type": "protagonist",
            "profile": {
                "age": 22,
                "gender": "male",
                "appearance": "身材瘦高，眼神坚毅，总是穿着一件洗得发白的蓝色衬衫",
                "personality": "坚韧不拔，心怀正义，善于观察细节",
                "mbti": "INFJ",
                "background": "出身贫寒，自幼丧父，靠母亲做缝纫维持生计。高中时偶然接触摄影，展现出非凡天赋",
                "goals": ["成为一名顶尖摄影师", "找到母亲的亲生父母", "用镜头记录人间真情"],
                "fears": ["失去母亲", "无法保护重要的人", "被现实压垮"],
                "skills": ["摄影", "观察力强", "写作"],
                "relationships": {}
            },
            "first_appearance": 1
        },
        {
            "name": "林婉儿",
            "role_type": "supporting",
            "profile": {
                "age": 21,
                "gender": "female",
                "appearance": "长发及腰，清秀温婉，总是带着淡淡的微笑",
                "personality": "温柔善良，心思细腻，但内心有着坚定的信念",
                "mbti": "ENFP",
                "background": "富家千金，却不喜奢华。大学时主修文学，热爱诗歌和古典音乐",
                "goals": ["出版自己的诗集", "帮助更多贫困学生", "找到真正属于自己的生活"],
                "fears": ["被家族束缚", "失去创作灵感", "伤害到身边的人"],
                "skills": ["写作", "钢琴", "绘画"],
                "relationships": {}
            },
            "first_appearance": 3
        },
        {
            "name": "张明",
            "role_type": "supporting",
            "profile": {
                "age": 23,
                "gender": "male",
                "appearance": "戴着一副黑框眼镜，看起来斯斯文文，但做起事来雷厉风行",
                "personality": "理性务实，有条理，是个典型的完美主义者",
                "mbti": "ENTJ",
                "background": "名校毕业，成绩优异。毕业后进入一家知名媒体公司，是李云的大学学长",
                "goals": ["成为媒体行业的领军人物", "证明自己的实力", "保护自己的朋友"],
                "fears": ["失败", "失去控制", "被人超越"],
                "skills": ["策划", "管理", "数据分析"],
                "relationships": {}
            },
            "first_appearance": 2
        }
    ]
    
    async with get_session() as db:
        char_service = CharacterService(db)
        
        # 清理已有的测试角色（避免重复）
        for char_data in test_characters:
            existing = await char_service.get_character_by_name(novel_id, char_data["name"])
            if existing:
                logger.info(f"删除已存在的角色: {char_data['name']}")
                await char_service.delete_character(existing.id)
        
        # 创建新角色
        created_chars = []
        for char_data in test_characters:
            char_create = CharacterCreate(
                novel_id=novel_id,
                **char_data
            )
            character = await char_service.create_character(char_create)
            created_chars.append(character)
            logger.success(f"创建角色成功: {character.name} (ID: {character.id})")
        
        # 验证角色列表
        logger.info("=" * 50)
        logger.info("验证角色列表...")
        logger.info("=" * 50)
        
        all_chars = await char_service.list_characters(novel_id)
        logger.info(f"当前共有 {len(all_chars)} 个角色:")
        
        for char in all_chars:
            logger.info(f"\n  角色: {char.name}")
            logger.info(f"    ID: {char.id}")
            logger.info(f"    类型: {char.role_type.value}")
            logger.info(f"    首次出场: 第{char.first_appearance}章")
            if char.profile:
                logger.info(f"    性别: {char.profile.get('gender', 'N/A')}")
                logger.info(f"    年龄: {char.profile.get('age', 'N/A')}")
        
        logger.info("\n" + "=" * 50)
        logger.success(f"测试完成！成功创建 {len(created_chars)} 个角色")
        logger.info("=" * 50)
        logger.info("\n现在请检查前端的角色管理页面，应该能看到以下角色:")
        for char in created_chars:
            logger.info(f"  - {char.name} ({char.role_type.value})")


if __name__ == "__main__":
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    try:
        asyncio.run(test_create_characters())
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        sys.exit(1)
