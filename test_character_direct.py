"""
直接调用角色设计服务
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
os.environ['LLM_PROVIDER'] = 'kimi'
os.environ['CHAT2API_BASE_URL'] = 'http://localhost:8088'

# 添加backend目录到Python路径
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
sys.path.insert(0, backend_dir)

from app.agents.unified_agent import UnifiedCharacterDesignerAgent


async def test_character_direct():
    """直接测试角色设计Agent"""

    agent = UnifiedCharacterDesignerAgent()

    context = {
        "user_input": "写一部现代都市励志小说，讲述一个出身贫寒的年轻人通过摄影实现梦想的故事",
        "genre": "现代都市",
        "num_characters": 2,
        "previous_phase_result": {
            "demand_analysis": {
                "analysis": {
                    "suggested_genre": "现代都市",
                    "target_audience": "青年读者"
                }
            }
        }
    }

    print("=" * 80)
    print("直接测试角色设计Agent")
    print("=" * 80)

    result = await agent.process(context)

    print(f"\n返回结果:")
    print(f"  success: {result.get('success')}")
    print(f"  error: {result.get('error')}")
    print(f"  characters 数量: {len(result.get('characters', []))}")

    if result.get('characters'):
        print(f"\n角色列表:")
        for idx, char in enumerate(result['characters'], 1):
            print(f"  {idx}. {char.get('name')} ({char.get('role_type')})")
            profile = char.get('profile', {})
            if profile:
                print(f"     年龄: {profile.get('age')}")
                print(f"     性别: {profile.get('gender')}")
    else:
        print(f"\n无角色数据！")
        if 'raw_response' in result:
            print(f"原始响应: {result['raw_response'][:500]}...")


if __name__ == "__main__":
    asyncio.run(test_character_direct())
