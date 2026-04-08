#!/usr/bin/env python3
"""测试角色同步到数据库"""
import asyncio
import sys
import os

# 添加backend路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# 设置环境变量
os.environ['DEBUG'] = 'true'
os.environ['MYSQL_HOST'] = 'localhost'
os.environ['MYSQL_PORT'] = '3306'
os.environ['MYSQL_USER'] = 'root'
os.environ['MYSQL_PASSWORD'] = 'root_password'
os.environ['MYSQL_DATABASE'] = 'novel_system'

from app.workflow_engine import WorkflowEngine
from app.workflow_engine import WorkflowPhase

async def main():
    print("=" * 80)
    print("测试角色同步到数据库")
    print("=" * 80)

    # 初始化工作流引擎
    engine = WorkflowEngine(novel_id=1, project_path="test")

    # 创建状态
    await engine.create_state()

    # 模拟角色设计结果
    test_data = {
        "characters": [
            {
                "name": "测试角色A",
                "role_type": "protagonist",
                "profile": {
                    "age": 25,
                    "gender": "male",
                    "appearance": "高大英俊",
                    "personality": "勇敢善良",
                    "background": "出身贵族",
                    "mbti": "ESTJ",
                    "goals": ["拯救世界"],
                    "fears": ["失败"],
                    "skills": ["剑术", "魔法"],
                    "relationships": {"盟友": "测试角色B"}
                }
            },
            {
                "name": "测试角色B",
                "role_type": "supporting",
                "profile": {
                    "age": 24,
                    "gender": "female",
                    "appearance": "美丽动人",
                    "personality": "聪明机智"
                }
            }
        ]
    }

    print("\n[1] 调用 transition_to 方法...")
    print(f"    数据: {list(test_data.keys())}")
    print(f"    角色数量: {len(test_data['characters'])}")

    # 调用 transition_to，这应该触发 _sync_characters_to_db
    await engine.transition_to(WorkflowPhase.CHARACTER_DESIGN, test_data)

    print("\n[2] 等待数据库更新...")
    await asyncio.sleep(2)

    # 检查数据库
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select, func
    from app.models.character import Character

    DATABASE_URL = "mysql+aiomysql://root:root_password@localhost:3306/novel_system"
    db_engine = create_async_engine(DATABASE_URL, echo=False)
    async_session_maker = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as db:
        result = await db.execute(
            select(func.count(Character.id)).where(Character.novel_id == 1)
        )
        count = result.scalar()

        print(f"\n[3] 数据库中的角色总数: {count}")

        # 查询新增的角色
        result = await db.execute(
            select(Character).where(Character.novel_id == 1).order_by(Character.id.desc()).limit(5)
        )
        chars = result.scalars().all()

        print("\n[4] 最新的5个角色:")
        for char in chars:
            print(f"    ID={char.id}, 名称={char.name}, 类型={char.role_type.value}")

        # 检查测试角色
        for test_char_name in ["测试角色A", "测试角色B"]:
            result = await db.execute(
                select(Character).where(
                    Character.novel_id == 1,
                    Character.name == test_char_name
                )
            )
            test_char = result.scalar_one_or_none()
            if test_char:
                print(f"\n    找到角色 '{test_char_name}': ID={test_char.id}")
            else:
                print(f"\n    未找到角色 '{test_char_name}'")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(main())
