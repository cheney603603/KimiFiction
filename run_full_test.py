#!/usr/bin/env python3
"""完整真实写作测试"""
import requests
import time
import sys

BASE = 'http://localhost:8080/api/v1'
NOVEL_ID = 1

def log(msg):
    print(msg, flush=True)

def poll_task(task_id, step_name, max_attempts=120, interval=10):
    """轮询任务"""
    log(f"Polling task: {task_id}")
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
                log(f'\n[OK] Task completed!')
                return True
            elif status == 'failed':
                log(f'\n[ERROR] Task failed: {step.get("error", "unknown")}')
                return False
        except Exception as e:
            log(f'  [{i}] error: {e}')
        
        time.sleep(interval)
    
    log('\n[WARN] Polling timeout')
    return False

def execute_phase(phase, user_input=""):
    """执行工作流阶段"""
    # 切换阶段
    log(f"\nSwitching to phase: {phase}")
    resp = requests.post(f'{BASE}/workflow/phase-switch/{NOVEL_ID}', 
                        json={'phase': phase}, timeout=10)
    log(f"Switch result: {resp.json().get('message', 'ok')}")
    
    # 执行阶段
    log(f"Executing phase: {phase}")
    payload = {
        'phase': phase,
        'input_data': {'user_input': user_input} if user_input else {},
        'timeout': 600
    }
    resp = requests.post(f'{BASE}/workflow/phase/{NOVEL_ID}', json=payload, timeout=30)
    result = resp.json()
    return result.get('task_id')

def write_chapter():
    """真实章节写作测试"""
    log("\n" + "="*70)
    log("REAL CHAPTER WRITING TEST (Writer-Reader Loop)")
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
    log(f"Summary: {outline.get('summary', 'None')[:150]}...")
    
    # 启动写作任务
    payload = {
        'chapter_number': 1,
        'writing_style': 'Narrative fluent, plot compact',
        'env_description_level': 'normal',
        'dialogue_ratio': 0.3,
        'notes': 'Real Writer-Reader loop test',
        'outline': outline,
        'auto_mode': False,
        'timeout': 900
    }
    
    resp = requests.post(f'{BASE}/workflow/chapter/{NOVEL_ID}', json=payload, timeout=30)
    if resp.status_code == 200:
        result = resp.json()
        task_id = result.get('task_id')
        log(f'\n[OK] Writing task started: {task_id}')
        return task_id
    else:
        log(f'[ERROR] {resp.status_code}: {resp.text[:300]}')
        return None

def main():
    log("="*70)
    log("FULL REAL LLM WRITING TEST")
    log("="*70)
    
    # Phase 1: outline_draft
    log("\n>>> PHASE 1: outline_draft")
    task_id = execute_phase('outline_draft')
    if task_id and not poll_task(task_id, 'phase_outline_draft'):
        log("[ERROR] outline_draft failed")
        return 1
    
    # Phase 2: outline_detail
    log("\n>>> PHASE 2: outline_detail")
    task_id = execute_phase('outline_detail', 'Generate detailed chapter outlines for chapters 1-3')
    if task_id and not poll_task(task_id, 'phase_outline_detail'):
        log("[ERROR] outline_detail failed")
        return 1
    
    # Phase 3: Real chapter writing with Writer-Reader loop
    task_id = write_chapter()
    if task_id:
        if poll_task(task_id, 'write_chapter', max_attempts=200, interval=10):
            log("\n" + "="*70)
            log("[SUCCESS] Real chapter writing test completed!")
            log("="*70)
            log("\nVisit the following pages to see results:")
            log("  - Chapter Writer: http://localhost:5173/novel/1/write")
            log("  - Workflow: http://localhost:5173/novel/1/workflow/new")
            return 0
    
    return 1

if __name__ == '__main__':
    sys.exit(main())
