#!/usr/bin/env python3
"""
真实写作测试脚本
测试 writer-reader 循环并将结果展示在ChapterWriter页面
"""
import asyncio
import json
import requests
from datetime import datetime

BASE_URL = "http://localhost:8080/api/v1"
NOVEL_ID = 1

def get_novel_info():
    """获取小说信息"""
    try:
        resp = requests.get(f"{BASE_URL}/novels/{NOVEL_ID}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        print(f"获取小说信息失败: {resp.status_code}")
        return None
    except Exception as e:
        print(f"获取小说信息异常: {e}")
        return None

def get_workflow_progress():
    """获取工作流进度"""
    try:
        resp = requests.get(f"{BASE_URL}/workflow/progress/{NOVEL_ID}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        print(f"获取工作流进度失败: {resp.status_code}")
        return None
    except Exception as e:
        print(f"获取工作流进度异常: {e}")
        return None

def get_chapter_outline(chapter_number):
    """获取章节细纲"""
    try:
        resp = requests.get(f"{BASE_URL}/workflow/phase-result/{NOVEL_ID}/outline_detail", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and data.get("data"):
                outlines = data["data"]
                if isinstance(outlines, dict) and "chapter_outlines" in outlines:
                    outlines = outlines["chapter_outlines"]
                if isinstance(outlines, list):
                    for outline in outlines:
                        if outline.get("chapter_number") == chapter_number:
                            return outline
        print(f"第{chapter_number}章缺少细纲")
        return None
    except Exception as e:
        print(f"获取章节细纲异常: {e}")
        return None

def write_chapter(chapter_number, writing_params=None):
    """调用API撰写章节"""
    try:
        outline = get_chapter_outline(chapter_number)
        if not outline:
            print(f"错误: 第{chapter_number}章缺少细纲，无法撰写")
            return None
        
        payload = {
            "chapter_number": chapter_number,
            "writing_style": writing_params.get("writing_style", "叙事流畅，情节紧凑") if writing_params else "叙事流畅，情节紧凑",
            "env_description_level": writing_params.get("env_description_level", "normal") if writing_params else "normal",
            "dialogue_ratio": writing_params.get("dialogue_ratio", 0.3) if writing_params else 0.3,
            "notes": writing_params.get("notes", "") if writing_params else "",
            "outline": outline,
            "auto_mode": False,
            "timeout": 900  # 15分钟超时
        }
        
        print(f"\n{'='*60}")
        print(f"开始撰写第{chapter_number}章")
        print(f"章节大纲: {outline.get('title', '未命名')}")
        print(f"细纲摘要: {outline.get('summary', '无')[:100]}...")
        print(f"{'='*60}\n")
        
        resp = requests.post(
            f"{BASE_URL}/workflow/chapter/{NOVEL_ID}",
            json=payload,
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()
            print(f"章节撰写任务已启动: {result.get('task_id')}")
            return result.get('task_id')
        else:
            print(f"启动章节撰写失败: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"撰写章节异常: {e}")
        return None

def get_task_progress(task_id):
    """获取任务进度"""
    try:
        resp = requests.get(f"{BASE_URL}/workflow/task-progress/{task_id}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"获取任务进度异常: {e}")
        return None

def poll_task_until_complete(task_id, interval=5, max_attempts=120):
    """轮询任务直到完成"""
    print(f"开始轮询任务进度: {task_id}")
    
    for attempt in range(max_attempts):
        progress = get_task_progress(task_id)
        if not progress:
            print(f"  尝试 {attempt+1}: 无法获取进度")
            asyncio.run(asyncio.sleep(interval))
            continue
        
        step = progress.get("steps", {}).get("write_chapter", {})
        status = step.get("status", "unknown")
        progress_text = step.get("progress", "初始化...")
        
        print(f"  [{attempt+1}] 状态: {status} | {progress_text}")
        
        # 打印日志
        logs = step.get("logs", [])
        if logs:
            last_log = logs[-1]
            print(f"       最新日志: [{last_log.get('level', 'info')}] {last_log.get('message', '')[:80]}")
        
        if status == "completed":
            print(f"\n[OK] 任务完成!")
            return progress
        elif status == "failed":
            print(f"\n[ERROR] 任务失败: {step.get('error', '未知错误')}")
            return progress
        
        asyncio.run(asyncio.sleep(interval))
    
    print(f"\n[WARN] 轮询超时，任务可能仍在运行")
    return None

def get_chapter_content(chapter_number):
    """获取章节内容"""
    try:
        # 先获取章节ID
        resp = requests.get(f"{BASE_URL}/chapters/novel/{NOVEL_ID}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            chapters = data.get("items", [])
            for ch in chapters:
                if ch.get("chapter_number") == chapter_number:
                    # 获取详细内容
                    detail_resp = requests.get(f"{BASE_URL}/chapters/{ch.get('id')}", timeout=10)
                    if detail_resp.status_code == 200:
                        return detail_resp.json()
        return None
    except Exception as e:
        print(f"获取章节内容异常: {e}")
        return None

def test_writer_reader_loop():
    """测试 writer-reader 循环"""
    print("\n" + "="*70)
    print("  Real Writing Test - Writer/Reader Loop")
    print("="*70)
    
    # 检查小说信息
    novel = get_novel_info()
    if novel:
        print(f"\n[小说] {novel.get('title', '未命名')}")
        print(f"   当前阶段: {novel.get('current_phase', '未知')}")
    
    # 检查工作流进度
    progress = get_workflow_progress()
    if progress:
        print(f"   已完成阶段: {', '.join(progress.get('completed_phases', []))}")
        print(f"   已完成章节: {progress.get('completed_chapters', 0)}")
    
    # 检查是否有章节细纲
    outline = get_chapter_outline(1)
    if not outline:
        print("\n[ERROR] 第1章缺少细纲，请先完成「章节细纲」阶段")
        print("   请访问: http://localhost:5173/novel/1/workflow/new")
        print("   完成「章节细纲」阶段后再运行此测试")
        return False
    
    print(f"\n[OK] 第1章细纲已找到: {outline.get('title', '未命名')}")
    print(f"   摘要: {outline.get('summary', '无')[:150]}...")
    
    # 配置写作参数
    writing_params = {
        "writing_style": "叙事流畅，情节紧凑",
        "env_description_level": "normal",
        "dialogue_ratio": 0.3,
        "notes": "真实写作测试 - 请生成高质量的内容"
    }
    
    # 启动章节撰写
    task_id = write_chapter(1, writing_params)
    if not task_id:
        return False
    
    # 轮询任务进度
    result = poll_task_until_complete(task_id)
    if not result:
        print("\n[WARN] 无法确认任务状态，请手动检查")
        return False
    
    # 获取最终章节内容
    chapter = get_chapter_content(1)
    if chapter:
        content = chapter.get("content", "")
        word_count = chapter.get("word_count", 0)
        print(f"\n[章节] 第1章撰写完成!")
        print(f"   标题: {chapter.get('title', '未命名')}")
        print(f"   字数: {word_count}")
        print(f"   内容预览:\n{'-'*60}")
        print(content[:500] + "..." if len(content) > 500 else content)
        print(f"{'-'*60}")
        
        # 检查是否有reader feedback
        step = result.get("steps", {}).get("write_chapter", {})
        logs = step.get("logs", [])
        reader_logs = [log for log in logs if "reader" in log.get("message", "").lower()]
        if reader_logs:
            print(f"\n[Reader反馈]:")
            for log in reader_logs[-3:]:
                print(f"   [{log.get('level')}] {log.get('message', '')[:100]}")
        
        print(f"\n[OK] 测试完成！")
        print(f"   请访问 http://localhost:5173/novel/1/write 查看完整内容")
        return True
    else:
        print("\n[WARN] 无法获取章节内容，请手动检查")
        return False

if __name__ == "__main__":
    success = test_writer_reader_loop()
    exit(0 if success else 1)
