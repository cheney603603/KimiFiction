#!/usr/bin/env python3
"""
配置LLM并执行真实写作测试
"""
import requests
import json
import time
import sys

BASE_URL = "http://localhost:8080/api/v1"
LLM_BASE_URL = "http://localhost:8080/api/v1/llm"
NOVEL_ID = 1

def setup_llm_config():
    """配置LLM使用8088端口"""
    config = {
        "provider": "kimi",
        "api_key": "dummy_key_for_chat2api",
        "baseUrl": "http://localhost:8088",
        "model": "kimi",
        "timeout": 600  # 10分钟超时，因为用户说延迟比较高
    }
    
    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/config",
            json=config,
            timeout=10
        )
        print(f"LLM配置结果: {resp.status_code}")
        if resp.status_code == 200:
            print("[OK] LLM配置已设置为 http://localhost:8088")
            return True
        else:
            print(f"[ERROR] 配置失败: {resp.text}")
            return False
    except Exception as e:
        print(f"[ERROR] 配置异常: {e}")
        return False

def test_llm_connection():
    """检查LLM配置"""
    try:
        print("\n检查LLM配置...")
        resp = requests.get(f"{LLM_BASE_URL}/config/timeout", timeout=10)
        if resp.status_code == 200:
            config = resp.json()
            print(f"当前配置: {json.dumps(config, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"检查配置失败: {resp.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] 检查异常: {e}")
        return False

def get_workflow_progress():
    """获取工作流进度"""
    try:
        resp = requests.get(f"{BASE_URL}/workflow/progress/{NOVEL_ID}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"[ERROR] 获取进度异常: {e}")
        return None

def get_phase_result(phase):
    """获取阶段结果"""
    try:
        resp = requests.get(f"{BASE_URL}/workflow/phase-result/{NOVEL_ID}/{phase}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"[ERROR] 获取阶段结果异常: {e}")
        return None

def execute_phase(phase, user_input="", timeout=600):
    """执行工作流阶段"""
    try:
        print(f"\n{'='*60}")
        print(f"执行阶段: {phase}")
        if user_input:
            print(f"用户输入: {user_input[:100]}...")
        print(f"{'='*60}")
        
        payload = {
            "phase": phase,
            "input_data": {"user_input": user_input} if user_input else {},
            "timeout": timeout
        }
        
        resp = requests.post(
            f"{BASE_URL}/workflow/phase/{NOVEL_ID}",
            json=payload,
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()
            task_id = result.get("task_id")
            print(f"[OK] 阶段 {phase} 已启动，任务ID: {task_id}")
            return task_id
        else:
            print(f"[ERROR] 启动失败: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"[ERROR] 执行异常: {e}")
        return None

def poll_task(task_id, max_attempts=120, interval=5):
    """轮询任务进度"""
    print(f"\n轮询任务: {task_id}")
    
    for attempt in range(max_attempts):
        try:
            resp = requests.get(f"{BASE_URL}/workflow/task-progress/{task_id}", timeout=10)
            if resp.status_code == 200:
                progress = resp.json()
                current_step = progress.get("current_step", "")
                step_info = progress.get("steps", {}).get(current_step, {})
                status = step_info.get("status", "unknown")
                progress_text = step_info.get("progress", "初始化...")
                
                # 打印最新日志
                logs = step_info.get("logs", [])
                if logs:
                    last_log = logs[-1]
                    print(f"  [{attempt+1}] {status} | {last_log.get('message', progress_text)[:80]}")
                else:
                    print(f"  [{attempt+1}] {status} | {progress_text}")
                
                if status == "completed":
                    print(f"\n[OK] 任务完成!")
                    return progress
                elif status == "failed":
                    print(f"\n[ERROR] 任务失败: {step_info.get('error', '未知错误')}")
                    return progress
                    
        except Exception as e:
            print(f"  [{attempt+1}] 轮询异常: {e}")
        
        time.sleep(interval)
    
    print(f"\n[WARN] 轮询超时")
    return None

def run_demand_analysis():
    """运行需求分析阶段"""
    print("\n" + "="*60)
    print("阶段1: 需求分析")
    print("="*60)
    
    user_input = """
请创作一部都市修仙小说，主角是一个普通大学生，意外获得了一个可以穿越到修仙世界的系统。
小说风格要轻松幽默，适合年轻读者阅读。
预计写100章左右，每章3000字。
"""
    
    task_id = execute_phase("demand_analysis", user_input, timeout=300)
    if task_id:
        return poll_task(task_id)
    return None

def run_world_building():
    """运行世界观构建阶段"""
    print("\n" + "="*60)
    print("阶段2: 世界观构建")
    print("="*60)
    
    task_id = execute_phase("world_building", "", timeout=400)
    if task_id:
        return poll_task(task_id)
    return None

def run_character_design():
    """运行角色设计阶段"""
    print("\n" + "="*60)
    print("阶段3: 角色设计")
    print("="*60)
    
    task_id = execute_phase("character_design", "", timeout=400)
    if task_id:
        return poll_task(task_id)
    return None

def run_outline_draft():
    """运行剧情大纲阶段"""
    print("\n" + "="*60)
    print("阶段4: 剧情大纲")
    print("="*60)
    
    task_id = execute_phase("outline_draft", "", timeout=500)
    if task_id:
        return poll_task(task_id)
    return None

def run_plot_design():
    """运行冲突伏笔设计阶段"""
    print("\n" + "="*60)
    print("阶段5: 冲突伏笔设计")
    print("="*60)
    
    task_id = execute_phase("plot_design", "", timeout=400)
    if task_id:
        return poll_task(task_id)
    return None

def run_outline_detail():
    """运行章节细纲阶段"""
    print("\n" + "="*60)
    print("阶段6: 章节细纲")
    print("="*60)
    
    task_id = execute_phase("outline_detail", "请为前10章生成详细的章节细纲", timeout=600)
    if task_id:
        return poll_task(task_id)
    return None

def write_chapter(chapter_number=1):
    """撰写指定章节 - 真实writer-reader循环"""
    print("\n" + "="*60)
    print(f"阶段7: 撰写第{chapter_number}章 (真实Writer-Reader循环)")
    print("="*60)
    
    # 获取章节细纲
    outline_result = get_phase_result("outline_detail")
    chapter_outline = None
    if outline_result and outline_result.get("data"):
        data = outline_result["data"]
        if isinstance(data, dict) and "chapter_outlines" in data:
            outlines = data["chapter_outlines"]
        elif isinstance(data, list):
            outlines = data
        else:
            outlines = []
        
        for o in outlines:
            if o.get("chapter_number") == chapter_number:
                chapter_outline = o
                break
    
    if not chapter_outline:
        print(f"[ERROR] 第{chapter_number}章缺少细纲")
        return None
    
    print(f"章节细纲: {chapter_outline.get('title', '未命名')}")
    print(f"摘要: {chapter_outline.get('summary', '无')[:150]}...")
    
    payload = {
        "chapter_number": chapter_number,
        "writing_style": "叙事流畅，情节紧凑，带有轻松幽默的风格",
        "env_description_level": "normal",
        "dialogue_ratio": 0.3,
        "notes": "这是真实LLM写作测试，请生成高质量章节内容",
        "outline": chapter_outline,
        "auto_mode": False,
        "timeout": 900  # 15分钟，因为writer-reader循环需要多次调用
    }
    
    try:
        resp = requests.post(
            f"{BASE_URL}/workflow/chapter/{NOVEL_ID}",
            json=payload,
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()
            task_id = result.get("task_id")
            print(f"[OK] 章节撰写任务已启动: {task_id}")
            return task_id
        else:
            print(f"[ERROR] 启动失败: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"[ERROR] 请求异常: {e}")
        return None

def main():
    """主函数"""
    print("="*70)
    print("  真实LLM写作测试")
    print("="*70)
    
    # 1. 配置LLM
    if not setup_llm_config():
        print("[ERROR] LLM配置失败")
        return 1
    
    # 2. 检查LLM配置
    if not test_llm_connection():
        print("[WARN] LLM配置检查未通过，但将继续尝试...")
    
    # 3. 检查当前工作流状态
    progress = get_workflow_progress()
    if progress:
        print(f"\n当前工作流状态:")
        print(f"  当前阶段: {progress.get('current_phase')}")
        print(f"  已完成阶段: {progress.get('completed_phases', [])}")
        print(f"  已完成章节: {progress.get('completed_chapters', 0)}")
    
    # 4. 执行缺失的阶段
    completed_phases = progress.get("completed_phases", []) if progress else []
    
    # 阶段顺序
    phases = [
        ("demand_analysis", run_demand_analysis),
        ("world_building", run_world_building),
        ("character_design", run_character_design),
        ("outline_draft", run_outline_draft),
        ("plot_design", run_plot_design),
        ("outline_detail", run_outline_detail),
    ]
    
    for phase_id, phase_func in phases:
        if phase_id not in completed_phases:
            print(f"\n执行缺失的阶段: {phase_id}")
            result = phase_func()
            if not result:
                print(f"[ERROR] 阶段 {phase_id} 执行失败")
                return 1
    
    # 5. 执行真实章节写作（Writer-Reader循环）
    print("\n" + "="*70)
    print("开始真实章节写作测试（Writer-Reader循环）")
    print("="*70)
    
    task_id = write_chapter(1)
    if task_id:
        result = poll_task(task_id, max_attempts=180, interval=10)  # 更长超时
        if result:
            print("\n[OK] 章节写作完成!")
            print("请访问 http://localhost:5173/novel/1/write 查看结果")
            return 0
    
    return 1

if __name__ == "__main__":
    sys.exit(main())
