"""
查询Redis中的工作流状态
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

from app.core.redis_client import RedisCache
import json


async def check_redis():
    """查询Redis中的工作流状态"""
    novel_id = 1

    print("=" * 80)
    print("查询Redis中的工作流状态")
    print("=" * 80)

    state_key = f"workflow_state:{novel_id}"

    # 获取工作流状态
    state_data = await RedisCache.get(state_key)

    if state_data:
        print(f"\n工作流状态 (key={state_key}):")
        try:
            state = json.loads(state_data)
            print(f"当前阶段: {state.get('current_phase')}")
            print(f"角色数量: {len(state.get('characters', []))}")

            print(f"\n角色列表:")
            for idx, char in enumerate(state.get('characters', []), 1):
                print(f"{idx}. {char.get('name')} ({char.get('role_type')})")
                profile = char.get('profile', {})
                if profile:
                    print(f"   年龄: {profile.get('age')}")
                    print(f"   性别: {profile.get('gender')}")
        except Exception as e:
            print(f"解析失败: {e}")
            print(f"原始数据: {state_data[:500]}...")
    else:
        print(f"未找到工作流状态 (key={state_key})")


if __name__ == "__main__":
    asyncio.run(check_redis())
