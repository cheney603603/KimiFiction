@echo off
chcp 65001 >nul
echo ========================================
echo    KimiFiction 停止脚本
echo ========================================
echo.

:: 停止Docker服务
echo 正在停止Docker服务...
docker-compose down
echo.

:: 关闭可能运行的后端和前端窗口
echo 正在关闭应用窗口...
taskkill /FI "WINDOWTITLE eq KimiFiction-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq KimiFiction-Frontend*" /F >nul 2>&1

echo.
echo ========================================
echo    已停止所有服务
echo ========================================
echo.
echo 数据已保存在Docker volumes中
echo 下次启动只需运行: start.bat
echo ========================================
pause
