"""
通过API测试角色同步到角色管理页面
"""
import asyncio
import sys
import os
import requests
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

from app.core.database import get_session
from app.models.character import Character
from sqlalchemy import select


async def test_character_sync_via_api():
    """通过API测试角色同步"""
    novel_id = 1
    api_base = "http://localhost:8080/api/v1"

    print("=" * 80)
    print("通过API测试角色同步")
    print("=" * 80)

    # 1. 执行角色设计
    print("\n[1] 执行角色设计...")
    url = f"{api_base}/workflow/phase/{novel_id}"
    payload = {
        "phase": "character_design",
        "input_data": {
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
            "num_characters": 3
        },
        "timeout": 300
    }

    response = requests.post(url, json=payload)
    print(f"   状态码: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"   成功: {result.get('success')}")
        print(f"   任务ID: {result.get('task_id')}")
        print(f"   状态: {result.get('status')}")
    else:
        print(f"   请求失败: {response.text}")
        return

    # 等待任务完成（角色设计大约需要60-90秒）
    print(f"\n[2] 等待角色设计完成（约90秒）...")
    for i in range(90, 0, -10):
        print(f"   倒计时: {i}秒...", end='\r')
        await asyncio.sleep(10)
    print("\n")

    # 等待数据库更新
    print("\n[3] 等待数据库更新...")
    await asyncio.sleep(5)

    # 4. 查询数据库中的角色
    print("\n[2] 查询数据库中的角色...")
    async with get_session() as db:
        stmt = select(Character).where(Character.novel_id == novel_id).order_by(Character.created_at.desc())
        result = await db.execute(stmt)
        characters = result.scalars().all()

        print(f"   总数: {len(characters)}")
        for idx, char in enumerate(characters, 1):
            print(f"   {idx}. {char.name} (ID: {char.id}, 类型: {char.role_type}, 创建时间: {char.created_at})")

    # 5. 通过API查询角色列表
    print("\n[3] 通过API查询角色列表...")
    url = f"{api_base}/characters/novel/{novel_id}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        characters = data.get("data", [])
        print(f"   API返回的角色数量: {len(characters)}")
        for idx, char in enumerate(characters, 1):
            print(f"   {idx}. {char.get('name')} (类型: {char.get('role_type')})")
    else:
        print(f"   API请求失败: {response.text}")

    print("\n" + "=" * 80)
    print("测试完成！请打开前端角色管理页面查看")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_character_sync_via_api())
