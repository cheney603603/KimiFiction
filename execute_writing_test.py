#!/usr/bin/env python3
"""执行真实写作测试"""
import requests
import time
import sys

BASE = 'http://localhost:8080/api/v1'
NOVEL_ID = 1

def check_phases():
    """检查各阶段状态"""
    phases = ['demand_analysis', 'world_building', 'character_design', 
              'outline_draft', 'plot_design', 'outline_detail']
    print("=" * 60)
    print("阶段状态检查")
    print("=" * 60)
    for phase in phases:
        resp = requests.get(f'{BASE}/workflow/phase-result/{NOVEL_ID}/{phase}', timeout=10)
        data = resp.json()
        has_data = data.get('data') is not None
        status = 'OK' if has_data else 'MISSING'
        print(f'  {phase}: {status}')
    print()

def execute_phase(phase, user_input=""):
    """执行阶段"""
    payload = {
        'phase': phase,
        'input_data': {'user_input': user_input} if user_input else {},
        'timeout': 600
    }
    print(f"启动阶段: {phase}")
    resp = requests.post(f'{BASE}/workflow/phase/{NOVEL_ID}', json=payload, timeout=30)
    result = resp.json()
    return result.get('task_id')

def poll_task(task_id, max_attempts=120):
    """轮询任务"""
    print(f"轮询任务: {task_id}")
    for i in range(max_attempts):
        try:
            resp = requests.get(f'{BASE}/workflow/task-progress/{task_id}', timeout=10)
            progress = resp.json()
            steps = progress.get('steps', {})
            current = progress.get('current_step', '')
            step = steps.get(current, {})
            status = step.get('status', 'unknown')
            logs = step.get('logs', [])
            
            if logs:
                msg = logs[-1].get('message', '')[:100]
                print(f'  [{i}] {status}: {msg}')
            else:
                print(f'  [{i}] {status}: waiting...')
            
            if status == 'completed':
                print(f'\n[OK] 阶段完成!')
                return True
            elif status == 'failed':
                print(f'\n[ERROR] 阶段失败: {step.get("error", "未知")}')
                return False
        except Exception as e:
            print(f'  [{i}] error: {e}')
        
        time.sleep(5)
    
    print('\n[WARN] 轮询超时')
    return False

def write_chapter():
    """真实章节写作"""
    # 获取细纲
    resp = requests.get(f'{BASE}/workflow/phase-result/{NOVEL_ID}/outline_detail', timeout=10)
    outline = None
    if resp.status_code == 200:
        data = resp.json()
        if data.get('data'):
            outlines = data['data']
            if isinstance(outlines, dict):
                outlines = outlines.get('chapter_outlines', [])
            for o in outlines:
                if o.get('chapter_number') == 1:
                    outline = o
                    break
    
    if not outline:
        print("[ERROR] 第1章缺少细纲")
        return None
    
    print("\n" + "=" * 60)
    print("真实章节写作: 第1章 (Writer-Reader循环)")
    print("=" * 60)
    print(f"标题: {outline.get('title', '未命名')}")
    print(f"摘要: {outline.get('summary', '无')[:150]}...")
    print()
    
    payload = {
        'chapter_number': 1,
        'writing_style': '叙事流畅，情节紧凑',
        'env_description_level': 'normal',
        'dialogue_ratio': 0.3,
        'notes': '真实Writer-Reader循环测试',
        'outline': outline,
        'auto_mode': False,
        'timeout': 900
    }
    
    resp = requests.post(f'{BASE}/workflow/chapter/{NOVEL_ID}', json=payload, timeout=30)
    if resp.status_code == 200:
        result = resp.json()
        task_id = result.get('task_id')
        print(f'[OK] 写作任务启动: {task_id}')
        return task_id
    else:
        print(f'[ERROR] {resp.status_code}: {resp.text[:300]}')
        return None

def main():
    print("=" * 70)
    print("  真实LLM Writer-Reader循环测试")
    print("=" * 70)
    print()
    
    # 检查阶段状态
    check_phases()
    
    # 执行outline_detail阶段（如果缺失）
    resp = requests.get(f'{BASE}/workflow/phase-result/{NOVEL_ID}/outline_detail', timeout=10)
    data = resp.json()
    if not data.get('data'):
        print("执行缺失的 outline_detail 阶段...")
        task_id = execute_phase('outline_detail', '请为第1章生成详细细纲')
        if task_id:
            if not poll_task(task_id):
                print("[ERROR] outline_detail 阶段失败")
                return 1
    
    # 真实章节写作
    task_id = write_chapter()
    if task_id:
        if poll_task(task_id, max_attempts=200):
            print("\n" + "=" * 70)
            print("[SUCCESS] 真实章节写作测试完成!")
            print("=" * 70)
            print()
            print("请访问以下页面查看结果:")
            print("  - 章节写作页面: http://localhost:5173/novel/1/write")
            print("  - 工作流页面: http://localhost:5173/novel/1/workflow/new")
            return 0
    
    return 1

if __name__ == '__main__':
    sys.exit(main())
