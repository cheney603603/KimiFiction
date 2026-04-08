#!/usr/bin/env python3
"""
简化的前端启动脚本
使用Python的http.server提供前端静态文件服务
"""
import http.server
import socketserver
import os
import webbrowser
import threading

PORT = 5173
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def log_message(self, format, *args):
        pass  # 静默日志

def run_server():
    with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
        print(f"前端服务已启动: http://localhost:{PORT}")
        print(f"按 Ctrl+C 停止服务")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n停止服务...")

if __name__ == "__main__":
    # 打开浏览器
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    
    # 运行服务器
    run_server()
