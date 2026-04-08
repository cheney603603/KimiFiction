@echo off
chcp 65001 >nul
echo ==========================================
echo    AI Chat API 服务启动脚本
echo ==========================================
echo.
echo 支持的 AI: Kimi, DeepSeek, 腾讯元宝
echo.

:: 激活 conda 环境
call conda activate quant

:: 检查 playwright 浏览器是否安装
echo 检查 Playwright 浏览器...
python -c "from playwright.sync_api import sync_playwright; sync_playwright().start().stop()" 2>nul
if errorlevel 1 (
    echo 正在安装 Playwright 浏览器...
    playwright install chromium
)

:: 启动服务
echo.
echo 启动服务...
echo 访问地址: http://localhost:8000
echo API 文档: http://localhost:8000/docs
echo.
python main.py

pause
