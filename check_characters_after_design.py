#!/usr/bin/env python3
"""检查角色设计后数据库中的角色"""
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

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.character import Character

async def main():
    print("=" * 80)
    print("检查数据库中的角色")
    print("=" * 80)

    # 创建数据库连接
    DATABASE_URL = "mysql+aiomysql://root:root_password@localhost:3306/novel_system"
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as db:
        # 查询novel_id=1的所有角色
        result = await db.execute(
            select(Character).where(Character.novel_id == 1).order_by(Character.id)
        )
        characters = result.scalars().all()

        print(f"\n数据库中novel_id=1的角色数量: {len(characters)}\n")

        for char in characters:
            print(f"ID: {char.id}")
            print(f"名称: {char.name}")
            print(f"类型: {char.role_type.value if hasattr(char.role_type, 'value') else char.role_type}")
            print(f"Profile: {char.profile}")
            print(f"创建时间: {char.created_at}")
            print("-" * 40)

        # 检查是否有"陆沉"这个角色
        luchen = await db.execute(
            select(Character).where(
                Character.novel_id == 1,
                Character.name == "陆沉"
            )
        )
        luchen_char = luchen.scalar_one_or_none()

        if luchen_char:
            print(f"\n✅ 找到角色 '陆沉':")
            print(f"   ID: {luchen_char.id}")
            print(f"   类型: {luchen_char.role_type.value if hasattr(luchen_char.role_type, 'value') else luchen_char.role_type}")
            print(f"   Profile: {luchen_char.profile}")
        else:
            print(f"\n❌ 未找到角色 '陆沉'")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    asyncio.run(main())
