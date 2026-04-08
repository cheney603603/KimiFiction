#!/usr/bin/env python3
"""最终真实写作测试 - 使用Kimi进行Writer-Reader循环"""
import requests
import time
import sys

BASE = 'http://localhost:8080/api/v1'
NOVEL_ID = 1

def log(msg):
    print(msg, flush=True)

def poll_task(task_id, step_name, max_attempts=200, interval=10):
    """轮询任务 - 最长33分钟"""
    log(f"Polling: {task_id}")
    for i in range(max_attempts):
        try:
            resp = requests.get(f'{BASE}/workflow/task-progress/{task_id}', timeout=10)
            progress = resp.json()
            step = progress.get('steps', {}).get(step_name, {})
            status = step.get('status', 'unknown')
            logs = step.get('logs', [])
            
            if logs:
                msg = logs[-1].get('message', '')[:100]
                log(f'  [{i}] {status}: {msg}')
            else:
                log(f'  [{i}] {status}')
            
            if status == 'completed':
                log(f'\n[SUCCESS] Task completed!')
                return True
            elif status == 'failed':
                err = step.get('error', 'unknown')
                log(f'\n[FAILED] {err}')
                return False
        except Exception as e:
            log(f'  [{i}] error: {e}')
        
        time.sleep(interval)
    
    log('\n[TIMEOUT] Polling timeout')
    return False

def execute_phase(phase, user_input=""):
    """执行工作流阶段"""
    log(f"\n>>> Executing phase: {phase}")
    
    # 切换阶段
    resp = requests.post(f'{BASE}/workflow/phase-switch/{NOVEL_ID}', 
                        json={'phase': phase}, timeout=10)
    
    # 执行
    payload = {
        'phase': phase,
        'input_data': {'user_input': user_input} if user_input else {},
        'timeout': 1800  # 30分钟
    }
    resp = requests.post(f'{BASE}/workflow/phase/{NOVEL_ID}', json=payload, timeout=30)
    result = resp.json()
    return result.get('task_id')

def write_chapter():
    """章节写作 - Writer-Reader循环"""
    log("\n" + "="*70)
    log("CHAPTER WRITING (Real Writer-Reader Loop with Kimi)")
    log("="*70)
    
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
        log("[ERROR] Chapter 1 outline missing")
        return None
    
    log(f"Title: {outline.get('title', 'Untitled')}")
    log(f"Summary: {str(outline.get('summary', ''))[:150]}...")
    
    payload = {
        'chapter_number': 1,
        'writing_style': '叙事流畅，情节紧凑，带有轻松幽默风格',
        'env_description_level': 'normal',
        'dialogue_ratio': 0.3,
        'notes': '真实Writer-Reader循环测试，使用Kimi生成',
        'outline': outline,
        'auto_mode': False,
        'timeout': 1800  # 30分钟支持多次循环
    }
    
    resp = requests.post(f'{BASE}/workflow/chapter/{NOVEL_ID}', json=payload, timeout=30)
    if resp.status_code == 200:
        result = resp.json()
        task_id = result.get('task_id')
        log(f'[OK] Writing task: {task_id}')
        return task_id
    else:
        log(f'[ERROR] {resp.status_code}: {resp.text[:300]}')
        return None

def main():
    log("="*70)
    log("REAL LLM WRITING TEST WITH KIMI")
    log("="*70)
    
    # Execute phases
    phases = [
        ('outline_draft', ''),
        ('outline_detail', 'Generate chapter outlines for chapters 1-3'),
    ]
    
    for phase, user_input in phases:
        task_id = execute_phase(phase, user_input)
        if task_id:
            step_name = f'phase_{phase}'
            if not poll_task(task_id, step_name):
                log(f"[ERROR] Phase {phase} failed")
                return 1
    
    # Chapter writing with Writer-Reader loop
    task_id = write_chapter()
    if task_id:
        if poll_task(task_id, 'write_chapter', max_attempts=200):
            log("\n" + "="*70)
            log("[SUCCESS] Chapter writing completed!")
            log("="*70)
            log("Visit: http://localhost:5173/novel/1/write")
            return 0
    
    return 1

if __name__ == '__main__':
    sys.exit(main())
