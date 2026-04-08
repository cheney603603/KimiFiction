#!/usr/bin/env python3
"""测试工作流角色设计后的数据同步"""
import asyncio
import sys
import os
import time
import requests

# 添加backend路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# 设置环境变量
os.environ['DEBUG'] = 'true'
os.environ['MYSQL_HOST'] = 'localhost'
os.environ['MYSQL_PORT'] = '3306'
os.environ['MYSQL_USER'] = 'root'
os.environ['MYSQL_PASSWORD'] = 'root_password'
os.environ['MYSQL_DATABASE'] = 'novel_system'
os.environ['LLM_PROVIDER'] = 'kimi'
os.environ['CHAT2API_BASE_URL'] = 'http://localhost:8088'

API_BASE = 'http://localhost:8080/api/v1'
NOVEL_ID = 1

async def main():
    print("=" * 80)
    print("测试工作流角色设计数据同步")
    print("=" * 80)

    # 1. 查询当前数据库中的角色数量
    print("\n[1] 查询当前数据库中的角色...")
    url = f"{API_BASE}/characters/novel/{NOVEL_ID}"
    response = requests.get(url)
    if response.status_code == 200:
        result = response.json()
        characters = result.get('items', [])
        print(f"   当前数据库中有 {len(characters)} 个角色:")
        for char in characters:
            print(f"      - {char['name']} ({char['role_type']}) ID: {char['id']}")
    else:
        print(f"   查询失败: {response.text}")
        return

    # 2. 查询工作流的角色设计结果
    print("\n[2] 查询工作流的角色设计结果...")
    url = f"{API_BASE}/workflow/progress/{NOVEL_ID}"
    response = requests.get(url)
    if response.status_code == 200:
        result = response.json()
        phases = result.get('phases', {})

        # 查找角色设计阶段
        character_design_phase = phases.get('character_design', {})
        status = character_design_phase.get('status', 'not_started')
        print(f"   角色设计阶段状态: {status}")

        if status == 'completed':
            # 获取阶段结果
            url = f"{API_BASE}/workflow/phase-result/{NOVEL_ID}/character_design"
            response = requests.get(url)
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    phase_data = result.get('data', {})
                    print(f"   阶段数据类型: {type(phase_data)}")

                    # 尝试提取角色数据
                    if isinstance(phase_data, dict):
                        wf_characters = phase_data.get('characters', [])
                    elif isinstance(phase_data, list):
                        wf_characters = phase_data
                    else:
                        wf_characters = []
                        print(f"   无法解析的数据: {phase_data}")

                    print(f"   工作流中有 {len(wf_characters)} 个角色:")
                    for char in wf_characters:
                        print(f"      - {char.get('name', 'unknown')} ({char.get('role_type', 'unknown')})")

                    # 3. 比对工作流和数据库的角色
                    print("\n[3] 比对工作流和数据库的角色...")
                    db_names = {c['name'] for c in characters}
                    wf_names = {c.get('name', '') for c in wf_characters}

                    only_in_workflow = wf_names - db_names
                    only_in_db = db_names - wf_names
                    common = db_names & wf_names

                    print(f"   只在工作流中的角色: {only_in_workflow}")
                    print(f"   只在数据库中的角色: {only_in_db}")
                    print(f"   共同的角色: {common}")

                    if only_in_workflow:
                        print(f"\n   ⚠️  警告: 有 {len(only_in_workflow)} 个角色未同步到数据库")
                        print("   这些角色应该在工作流完成后自动保存")
                    elif common:
                        print(f"\n   ✅ 角色已正确同步到数据库")
            else:
                print(f"   获取阶段结果失败: {response.text}")
        else:
            print(f"   角色设计阶段未完成")
    else:
        print(f"   查询工作流状态失败: {response.text}")
        return

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(main())
