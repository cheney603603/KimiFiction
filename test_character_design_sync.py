"""
诊断角色设计阶段数据是否正确保存到数据库
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import get_session
from app.models.character import Character
from app.models.novel import Novel
from app.core.redis_client import WorkflowState, SessionManager
import json


async def check_character_design(novel_id: int):
    """检查角色设计阶段的数据"""

    print(f"\n{'='*60}")
    print(f"检查小说 {novel_id} 的角色设计数据")
    print(f"{'='*60}\n")

    # 1. 检查工作流状态中的角色数据
    print("1. 检查工作流状态:")
    state_key = f"workflow_state:{novel_id}"
    state = await WorkflowState.load(state_key)

    if state:
        print(f"   ✅ 工作流状态存在")
        print(f"   当前阶段: {state.get('current_phase', 'unknown')}")

        characters = state.get('characters')
        if characters:
            print(f"   ✅ state.characters 存在, 类型: {type(characters)}")
            print(f"   角色数量: {len(characters) if isinstance(characters, list) else 'N/A'}")

            if isinstance(characters, list) and len(characters) > 0:
                print(f"\n   角色数据预览:")
                for i, char in enumerate(characters[:2], 1):  # 只显示前2个
                    print(f"   角色 {i}:")
                    print(f"      name: {char.get('name', 'N/A')}")
                    print(f"      role_type: {char.get('role_type', 'N/A')}")
                    if 'profile' in char:
                        print(f"      profile keys: {list(char['profile'].keys()) if isinstance(char['profile'], dict) else 'N/A'}")
            else:
                print(f"   ⚠️  characters 是空数组或不是列表")
        else:
            print(f"   ❌ state.characters 不存在或为 None")
    else:
        print(f"   ❌ 工作流状态不存在")

    # 2. 检查数据库中的角色数据
    print(f"\n2. 检查数据库中的角色:")
    async with get_session() as db:
        result = await db.execute(
            select(Character).where(Character.novel_id == novel_id)
        )
        db_characters = result.scalars().all()

        print(f"   数据库中的角色数量: {len(db_characters)}")

        if db_characters:
            print(f"\n   数据库角色详情:")
            for char in db_characters[:3]:
                print(f"   - ID: {char.id}, Name: {char.name}, Role: {char.role_type}")
                if char.profile:
                    print(f"     Profile keys: {list(char.profile.keys()) if isinstance(char.profile, dict) else 'N/A'}")
        else:
            print(f"   ⚠️  数据库中没有角色数据")

    # 3. 检查已完成阶段
    print(f"\n3. 检查已完成阶段:")
    phase_history = state.get('phase_history', []) if state else []
    print(f"   已完成阶段: {phase_history}")

    if 'character_design' in phase_history:
        print(f"   ✅ character_design 阶段已完成")
    else:
        print(f"   ❌ character_design 阶段未完成")

    # 4. 检查阶段结果
    print(f"\n4. 检查阶段结果:")
    phase_result_key = f"phase_result:{novel_id}:character_design"
    try:
        from app.core.redis_client import get_redis
        redis = get_redis()
        result = await redis.get(phase_result_key)
        if result:
            result_data = json.loads(result)
            print(f"   ✅ 阶段结果存在")
            print(f"   数据类型: {type(result_data)}")
            if 'characters' in result_data:
                print(f"   角色数量: {len(result_data['characters']) if isinstance(result_data['characters'], list) else 'N/A'}")
        else:
            print(f"   ⚠️  阶段结果不存在")
    except Exception as e:
        print(f"   ❌ 读取阶段结果失败: {e}")

    # 5. 总结
    print(f"\n{'='*60}")
    print("诊断总结:")
    print(f"{'='*60}")

    state_has_chars = state and state.get('characters') and len(state.get('characters', [])) > 0
    db_has_chars = len(db_characters) > 0
    phase_completed = 'character_design' in phase_history

    if state_has_chars and db_has_chars and phase_completed:
        print("✅ 角色设计完整：工作流状态有数据，数据库有数据，阶段已完成")
    elif state_has_chars and not db_has_chars:
        print("⚠️  问题：工作流状态有数据，但数据库没有")
        print("   可能原因：_sync_characters_to_db 方法未调用或失败")
    elif not state_has_chars and db_has_chars:
        print("⚠️  异常：工作流状态没有数据，但数据库有数据")
    else:
        print("❌ 角色设计失败：既没有工作流状态数据，也没有数据库数据")
        print("   可能原因：")
        print("   1. 角色设计阶段未执行")
        print("   2. JSON解析失败")
        print("   3. LLM返回格式不正确")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_character_design_sync.py <novel_id>")
        print("示例: python test_character_design_sync.py 1")
        sys.exit(1)

    novel_id = int(sys.argv[1])
    asyncio.run(check_character_design(novel_id))
