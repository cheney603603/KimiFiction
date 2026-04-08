#!/usr/bin/env python3
"""
规则怪谈beta - 继续写作脚本
重新写作第9-20章，然后继续写21-30章
"""
import json
import time
import sys
import os
import urllib.request
import urllib.error
from datetime import datetime

API_BASE = "http://localhost:8081/api/v1"  # 使用8081端口
NOVEL_TITLE = "规则怪谈beta"
NOVEL_ID = 3
START_CHAPTER = 9  # 从第9章开始（需要重写）
TARGET_CHAPTERS = 30  # 目标写到30章

# 日志文件
LOG_FILE = f"D:/310Programm/KimiFiction/continue_writing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def api_call(method, path, data=None, token=None, timeout=600):
    """Call API with error handling"""
    url = f"{API_BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        log(f"  API Error {e.code}: {error_body}")
        return {"error": True, "status": e.code, "detail": error_body}
    except Exception as e:
        log(f"  Request failed: {e}")
        return {"error": True, "detail": str(e)}

def login():
    """Login and get token"""
    log("=== 登录 ===")
    result = api_call("POST", "/auth/login", {
        "username": "novelwriter",
        "password": "novel123456"
    })
    if "access_token" in result:
        log(f"  登录成功, user_id={result.get('user',{}).get('id')}")
        return result["access_token"]
    log(f"  登录失败: {result}")
    sys.exit(1)

def set_llm_config(token):
    """Set LLM config"""
    log("=== 配置 LLM ===")
    result = api_call("POST", "/llm/config", {
        "provider": "openai",
        "apiKey": "not-needed",
        "baseUrl": "http://localhost:8088",
        "model": "kimi",
        "responseTime": 30,
        "timeout": 300
    }, token)
    if result.get("success"):
        log(f"  LLM 配置成功, timeout={result.get('timeout')}s")
    else:
        log(f"  LLM 配置失败: {result}")

def poll_task(task_id, token, max_wait=600, poll_interval=5):
    """Poll task until complete"""
    start = time.time()
    while time.time() - start < max_wait:
        result = api_call("GET", f"/workflow/task-progress/{task_id}", token=token)
        if result.get("error"):
            log(f"  Poll error: {result}")
            time.sleep(poll_interval)
            continue
        
        status = result.get("status", "unknown")
        steps = result.get("steps", [])
        current_step = result.get("current_step", "")
        
        # Get current step status
        step_info = ""
        for s in steps:
            if isinstance(s, dict) and s.get("step_id") == current_step:
                step_info = f" - {s.get('name','')}: {s.get('status','')}"
                sub = s.get("current_substep", 0)
                total = s.get("total_substeps", 0)
                if total > 0:
                    step_info += f" ({sub}/{total})"
                break
        
        elapsed = int(time.time() - start)
        log(f"  [{elapsed}s] Status={status}{step_info}")
        
        if status == "completed":
            return result
        elif status == "failed":
            # Get error from steps
            for s in steps:
                if isinstance(s, dict) and s.get("status") == "failed":
                    return {"status": "failed", "error": s.get("error", "Unknown error")}
            return {"status": "failed", "error": "Unknown error"}
        
        time.sleep(poll_interval)
    
    return {"status": "timeout", "error": f"Task did not complete within {max_wait}s"}

def write_single_chapter(token, chapter_num, max_wait=900):
    """Write a single chapter"""
    log(f"\n>>> 撰写第 {chapter_num} 章")
    data = {
        "chapter_number": chapter_num,
        "writing_style": "悬疑惊悚",
        "env_description_level": "detailed",
        "dialogue_ratio": 0.3,
        "auto_mode": True,
        "timeout": 300
    }
    
    result = api_call("POST", f"/workflow/chapter/{NOVEL_ID}", data, token)
    if result.get("error"):
        return False, f"Chapter start failed: {result}"
    
    task_id = result.get("task_id")
    if not task_id:
        return False, "No task_id returned"
    
    log(f"  Task ID: {task_id}")
    poll_result = poll_task(task_id, token, max_wait=max_wait)
    
    if poll_result.get("status") == "completed":
        log(f"  第 {chapter_num} 章撰写完成!")
        return True, poll_result
    else:
        error = poll_result.get("error", "Unknown error")
        log(f"  第 {chapter_num} 章失败: {error}")
        return False, error

def main():
    log("=" * 60)
    log(f"规则怪谈beta - 继续写作")
    log(f"从第{START_CHAPTER}章写到第{TARGET_CHAPTERS}章")
    log(f"小说 ID: {NOVEL_ID}")
    log(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)
    
    # Step 1: Login
    token = login()
    
    # Step 2: Set LLM config
    set_llm_config(token)
    
    # Step 3: Write chapters
    log("\n" + "=" * 60)
    log("开始撰写章节...")
    log("=" * 60)
    
    success_count = 0
    fail_count = 0
    start_time = time.time()
    total_chapters = TARGET_CHAPTERS - START_CHAPTER + 1
    
    for chapter_num in range(START_CHAPTER, TARGET_CHAPTERS + 1):
        elapsed = int(time.time() - start_time)
        remaining = total_chapters - (chapter_num - START_CHAPTER)
        log(f"\n--- 进度: {chapter_num}/{TARGET_CHAPTERS} (剩余{remaining}章, 已用时: {elapsed//60}分钟) ---")
        
        success, result = write_single_chapter(token, chapter_num, max_wait=900)
        if success:
            success_count += 1
        else:
            fail_count += 1
            log(f"  等待30秒后重试...")
            time.sleep(30)
            # Retry once
            success, result = write_single_chapter(token, chapter_num, max_wait=900)
            if success:
                success_count += 1
                fail_count -= 1
            else:
                log(f"  重试仍然失败，跳过第 {chapter_num} 章")
    
    # Summary
    total_elapsed = int(time.time() - start_time)
    log("\n" + "=" * 60)
    log("写作完成!")
    log(f"  成功: {success_count}/{total_chapters}")
    log(f"  失败: {fail_count}/{total_chapters}")
    log(f"  总用时: {total_elapsed//3600}小时{(total_elapsed%3600)//60}分钟")
    log(f"  日志文件: {LOG_FILE}")
    log("=" * 60)

if __name__ == "__main__":
    main()
