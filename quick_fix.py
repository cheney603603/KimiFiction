#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速修复脚本
检查并修复Chat2API连接配置问题
"""
import os
import sys
import json

# 设置输出编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_file_exists(filepath):
    """检查文件是否存在"""
    exists = os.path.exists(filepath)
    print(f"[OK] {filepath}" if exists else f"[FAIL] {filepath}")
    return exists

def check_port_in_use(port):
    """检查端口是否被占用"""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = s.connect_ex(('127.0.0.1', port))
        s.close()
        in_use = result == 0
        print(f"[OK] 端口 {port}: {'使用中' if in_use else '未使用'}")
        return in_use
    except Exception as e:
        print(f"[FAIL] 检查端口 {port} 失败: {e}")
        return False

def check_env_file():
    """检查.env文件配置"""
    print("\n=== 检查 backend/.env ===")
    env_path = os.path.join(os.path.dirname(__file__), 'backend', '.env')
    if not check_file_exists(env_path):
        return False

    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    config = {}
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            config[key.strip()] = value.strip()

    provider = config.get('LLM_PROVIDER', '未设置')
    base_url = config.get('CHAT2API_BASE_URL', '未设置')

    print(f"  LLM_PROVIDER: {provider}")
    print(f"  CHAT2API_BASE_URL: {base_url}")

    # 检查端口配置
    if 'localhost:8000' in base_url:
        print("  [WARN] Base URL 使用了错误的端口 8000")
        print("  [INFO] 建议: 修改为 8088")
        return False
    elif 'localhost:8088' in base_url:
        print("  [OK] Base URL 端口配置正确")
        return True
    elif 'host.docker.internal:8088' in base_url:
        print("  [OK] Base URL 配置为Docker兼容模式")
        return True
    else:
        print(f"  [WARN] 未知的Base URL配置: {base_url}")
        return False

def check_frontend_config():
    """检查前端默认配置"""
    print("\n=== 检查前端默认配置 ===")
    llm_settings_path = os.path.join(os.path.dirname(__file__), 'frontend', 'src', 'pages', 'LLMSettings.tsx')

    if not check_file_exists(llm_settings_path):
        return False

    with open(llm_settings_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查默认端口
    if 'http://localhost:8000' in content:
        print("  [WARN] 前端默认端口仍为 8000")
        print("  [INFO] 建议: 已在之前的修复中更新，请确认文件已保存")
        return False
    elif 'http://localhost:8088' in content:
        print("  [OK] 前端默认端口配置正确 (8088)")
        return True
    else:
        print("  [?] 未找到前端默认端口配置")
        return False

def check_workflow_sync():
    """检查WorkflowPage配置同步"""
    print("\n=== 检查WorkflowPage配置同步 ===")
    workflow_path = os.path.join(os.path.dirname(__file__), 'frontend', 'src', 'pages', 'WorkflowPage.tsx')

    if not check_file_exists(workflow_path):
        return False

    with open(workflow_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否有同步配置的代码
    if 'llmConfigApi.saveConfig' in content:
        print("  [OK] WorkflowPage 包含配置同步代码")
        return True
    else:
        print("  [WARN] WorkflowPage 缺少配置同步代码")
        return False

def print_summary(results):
    """打印总结"""
    print("\n" + "="*60)
    print("检查总结")
    print("="*60)

    all_pass = all(results.values())

    for key, value in results.items():
        status = "[PASS] 通过" if value else "[FAIL] 失败"
        print(f"{key}: {status}")

    print("\n" + "="*60)
    if all_pass:
        print("[SUCCESS] 所有检查通过！")
        print("\n下一步:")
        print("1. 启动Chat2API服务: cd chat2api_service && python main.py")
        print("2. 访问 http://localhost:8088 并登录")
        print("3. 访问 http://localhost:5173/settings/llm 配置LLM")
        print("4. 访问 http://localhost:5173/novel/1/workflow/new 执行工作流")
    else:
        print("[WARN] 部分检查未通过，请根据上面的提示进行修复")
        print("\n详细修复指南请参考: WORKFLOW_FIX_GUIDE.md")
        print("\n验证步骤请参考: VERIFICATION_STEPS.md")
    print("="*60)

def main():
    """主函数"""
    print("="*60)
    print("Chat2API连接配置检查工具")
    print("="*60)

    results = {}

    # 检查端口
    print("\n=== 检查服务端口 ===")
    chat2api_running = check_port_in_use(8088)
    backend_running = check_port_in_use(8080)
    frontend_running = check_port_in_use(5173)

    results['Chat2API (8088)'] = chat2api_running
    results['后端服务 (8080)'] = backend_running
    results['前端服务 (5173)'] = frontend_running

    # 检查配置文件
    results['后端.env配置'] = check_env_file()
    results['前端默认配置'] = check_frontend_config()
    results['WorkflowPage同步'] = check_workflow_sync()

    # 打印总结
    print_summary(results)

    # 询问是否需要修复
    if not all(results.values()):
        print("\n" + "="*60)
        response = input("是否需要自动修复前端默认端口配置? (y/n): ").strip().lower()
        if response == 'y':
            fix_frontend_config()

def fix_frontend_config():
    """修复前端配置"""
    print("\n正在修复前端配置...")
    llm_settings_path = os.path.join(os.path.dirname(__file__), 'frontend', 'src', 'pages', 'LLMSettings.tsx')

    try:
        with open(llm_settings_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 替换端口
        if 'http://localhost:8000' in content:
            content = content.replace('http://localhost:8000', 'http://localhost:8088')

            with open(llm_settings_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print("[OK] 前端配置已修复")
        else:
            print("[INFO] 前端配置已是正确的，无需修复")
    except Exception as e:
        print(f"[FAIL] 修复失败: {e}")

if __name__ == "__main__":
    main()
