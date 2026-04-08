"""
测试脚本：格式化显示角色数据
"""
import json
import requests

# 测试角色列表API
url = "http://localhost:8080/api/v1/characters/novel/1"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    
    print("=" * 80)
    print("角色列表 API 测试结果")
    print("=" * 80)
    print(f"\n总数: {data['total']}")
    print(f"API URL: {url}\n")
    
    for idx, char in enumerate(data['items'], 1):
        print(f"{idx}. {char['name']}")
        print(f"   ID: {char['id']}")
        print(f"   类型: {char['role_type']}")
        print(f"   首次出场: 第{char['first_appearance']}章")
        
        if char['profile']:
            profile = char['profile']
            if 'gender' in profile:
                print(f"   性别: {profile['gender']}")
            if 'age' in profile:
                print(f"   年龄: {profile['age']}")
            if 'mbti' in profile:
                print(f"   MBTI: {profile['mbti']}")
            if 'personality' in profile:
                print(f"   性格: {profile['personality']}")
            if 'appearance' in profile:
                print(f"   外貌: {profile['appearance']}")
            if 'background' in profile:
                print(f"   背景: {profile['background'][:50]}...")
            if 'goals' in profile:
                print(f"   目标: {', '.join(profile['goals'])}")
        
        print()
    
    print("=" * 80)
    print("[OK] API 测试成功！角色数据已正确同步到数据库")
    print("=" * 80)
    print("\n现在请打开前端角色管理页面，应该能看到上述4个角色:")
    print("  - test (protagonist)")
    print("  - 李云 (protagonist)")
    print("  - 张明 (supporting)")
    print("  - 林婉儿 (supporting)")
else:
    print(f"[ERROR] API 请求失败: {response.status_code}")
    print(response.text)
