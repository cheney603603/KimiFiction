#!/usr/bin/env python3
"""重启后端服务"""
import os
import signal
import time
import subprocess
import sys

# 杀死占用8000端口的进程
def kill_port_8000():
    try:
        # Windows: 使用netstat和taskkill
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True
        )
        for line in result.stdout.split('\n'):
            if ':8000' in line and 'LISTENING' in line:
                parts = line.split()
                if parts:
                    pid = parts[-1]
                    try:
                        print(f"杀死进程 {pid}")
                        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                    except:
                        pass
    except Exception as e:
        print(f"警告: {e}")

# 等待一下
time.sleep(2)

# 启动新的后端
print("启动后端服务...")
os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))
os.system('python main.py')
