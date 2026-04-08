"""
直接查询数据库中的角色和工作流状态
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

from app.core.database import get_session
from app.models.character import Character
from sqlalchemy import select, text
import json


async def check_database():
    """查询数据库中的角色和工作流状态"""
    novel_id = 1

    print("=" * 80)
    print("查询数据库状态")
    print("=" * 80)

    async with get_session() as db:
        # 查询角色
        stmt = select(Character).where(Character.novel_id == novel_id).order_by(Character.created_at.desc())
        result = await db.execute(stmt)
        characters = result.scalars().all()

        print(f"\n数据库中的角色 (novel_id={novel_id}):")
        print(f"总数: {len(characters)}")
        for idx, char in enumerate(characters, 1):
            print(f"\n{idx}. {char.name} (ID: {char.id})")
            print(f"   类型: {char.role_type}")
            print(f"   创建时间: {char.created_at}")

        # 直接查询workflow_states表
        print("\n\n直接查询workflow_states表:")
        try:
            result = await db.execute(text("SELECT phase, status, result_data, created_at, updated_at FROM workflow_states WHERE novel_id = :novel_id"), {"novel_id": novel_id})
            rows = result.fetchall()
            print(f"找到 {len(rows)} 条记录")
            for row in rows:
                print(f"\n  阶段: {row[0]}")
                print(f"  状态: {row[1]}")
                print(f"  创建时间: {row[3]}")
                if row[2]:
                    print(f"  结果数据长度: {len(row[2])}")
                    # 尝试解析JSON
                    try:
                        data = json.loads(row[2])
                        if isinstance(data, dict) and 'characters' in data:
                            print(f"  角色数量: {len(data['characters'])}")
                            for char in data['characters']:
                                print(f"    - {char.get('name')} ({char.get('role_type')})")
                    except:
                        print(f"  (无法解析)")
        except Exception as e:
            print(f"查询workflow_states表失败: {e}")


if __name__ == "__main__":
    asyncio.run(check_database())
