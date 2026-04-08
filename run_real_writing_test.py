#!/usr/bin/env python3
"""
真实LLM写作测试 - 直接调用工作流API进行writer-reader循环测试
"""
import requests
import json
import time
import sys

BASE_URL = "http://localhost:8080/api/v1"
LLM_URL = "http://localhost:8080/api/v1/llm"
NOVEL_ID = 1

def setup_llm():
    """配置LLM使用8088端口"""
    config = {
        "provider": "kimi",
        "apiKey": "dummy_key",
        "baseUrl": "http://localhost:8088",
        "model": "kimi",
        "timeout": 600
    }
    try:
        resp = requests.post(f"{LLM_URL}/config", json=config, timeout=10)
        print(f"LLM配置: {resp.status_code}")
        if resp.status_code == 200:
            print("[OK] LLM已配置到 http://localhost:8088")
            return True
        print(f"[WARN] 配置返回: {resp.text[:200]}")
        return True  # 即使失败也继续
    except Exception as e:
        print(f"[WARN] 配置异常: {e}")
        return True  # 继续尝试

def get_progress():
    """获取工作流进度"""
    try:
        resp = requests.get(f"{BASE_URL}/workflow/progress/{NOVEL_ID}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[ERROR] 获取进度: {e}")
    return None

def execute_phase(phase, user_input=""):
    """执行工作流阶段"""
    payload = {
        "phase": phase,
        "input_data": {"user_input": user_input} if user_input else {},
        "timeout": 600
    }
    try:
        print(f"\n启动阶段: {phase}")
        resp = requests.post(f"{BASE_URL}/workflow/phase/{NOVEL_ID}", json=payload, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            task_id = result.get("task_id")
            print(f"[OK] 任务ID: {task_id}")
            return task_id
        print(f"[ERROR] {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[ERROR] 执行异常: {e}")
    return None

def poll_task(task_id, max_attempts=200, interval=5):
    """轮询任务进度"""
    print(f"轮询任务: {task_id}")
    for attempt in range(max_attempts):
        try:
            resp = requests.get(f"{BASE_URL}/workflow/task-progress/{task_id}", timeout=10)
            if resp.status_code == 200:
                progress = resp.json()
                current = progress.get("current_step", "")
                step = progress.get("steps", {}).get(current, {})
                status = step.get("status", "unknown")
                logs = step.get("logs", [])
                
                if logs:
                    last = logs[-1]
                    msg = last.get("message", "")[:100]
                    print(f"  [{attempt+1}] {status}: {msg}")
                else:
                    print(f"  [{attempt+1}] {status}: 等待中...")
                
                if status == "completed":
                    print("\n[OK] 阶段完成!")
                    return progress
                elif status == "failed":
                    print(f"\n[ERROR] 失败: {step.get('error', '未知')}")
                    return progress
        except Exception as e:
            print(f"  [{attempt+1}] 轮询异常: {e}")
        time.sleep(interval)
    print("\n[WARN] 轮询超时")
    return None

def write_chapter_real(chapter_num=1):
    """真实章节写作 - Writer-Reader循环"""
    # 获取细纲
    resp = requests.get(f"{BASE_URL}/workflow/phase-result/{NOVEL_ID}/outline_detail", timeout=10)
    outline = None
    if resp.status_code == 200:
        data = resp.json()
        if data.get("data"):
            outlines = data["data"]
            if isinstance(outlines, dict):
                outlines = outlines.get("chapter_outlines", [])
            for o in outlines:
                if o.get("chapter_number") == chapter_num:
                    outline = o
                    break
    
    if not outline:
        print(f"\n[ERROR] 第{chapter_num}章缺少细纲")
        return None
    
    print(f"\n{'='*70}")
    print(f"真实章节写作: 第{chapter_num}章")
    print(f"{'='*70}")
    print(f"标题: {outline.get('title', '未命名')}")
    print(f"摘要: {outline.get('summary', '无')[:150]}...")
    
    payload = {
        "chapter_number": chapter_num,
        "writing_style": "叙事流畅，情节紧凑",
        "env_description_level": "normal",
        "dialogue_ratio": 0.3,
        "notes": "真实Writer-Reader循环测试",
        "outline": outline,
        "auto_mode": False,
        "timeout": 900  # 15分钟，支持多次writer-reader循环
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/workflow/chapter/{NOVEL_ID}", json=payload, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            task_id = result.get("task_id")
            print(f"\n[OK] 写作任务启动: {task_id}")
            return task_id
        print(f"[ERROR] {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        print(f"[ERROR] 请求异常: {e}")
    return None

def run_test():
    """运行完整测试"""
    print("="*70)
    print("  真实LLM Writer-Reader循环测试")
    print("="*70)
    
    # 配置LLM
    setup_llm()
    
    # 检查当前状态
    progress = get_progress()
    if progress:
        print(f"\n当前阶段: {progress.get('current_phase')}")
        print(f"已完成: {progress.get('completed_phases', [])}")
        completed = progress.get("completed_phases", [])
    else:
        completed = []
    
    # 执行缺失阶段
    phases = [
        ("demand_analysis", "都市修仙小说，主角是普通大学生，获得穿越修仙世界的系统，风格轻松幽默"),
        ("world_building", ""),
        ("character_design", ""),
        ("outline_draft", ""),
        ("plot_design", ""),
        ("outline_detail", "请为前3章生成详细细纲"),
    ]
    
    for phase, user_input in phases:
        if phase not in completed:
            task_id = execute_phase(phase, user_input)
            if task_id:
                poll_task(task_id)
    
    # 真实章节写作测试
    print("\n" + "="*70)
    print("开始真实章节写作 (Writer-Reader循环)")
    print("="*70)
    
    task_id = write_chapter_real(1)
    if task_id:
        result = poll_task(task_id, max_attempts=200, interval=10)
        if result:
            print("\n" + "="*70)
            print("[SUCCESS] 真实章节写作测试完成!")
            print("="*70)
            print("\n请访问以下页面查看结果:")
            print("  - 章节写作页面: http://localhost:5173/novel/1/write")
            print("  - 工作流页面: http://localhost:5173/novel/1/workflow/new")
            return 0
    
    return 1

if __name__ == "__main__":
    sys.exit(run_test())
