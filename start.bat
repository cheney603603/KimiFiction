@echo off
chcp 65001 >nul
echo ========================================
echo    KimiFiction 一键启动脚本
echo ========================================
echo.

:: 检查Docker是否安装
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Docker，请先安装Docker Desktop
    echo 下载地址: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

:: 检查Docker是否运行
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker未运行，请先启动Docker Desktop
    pause
    exit /b 1
)

echo [1/4] 启动Docker服务 (MySQL, Redis, Qdrant)...
docker-compose up -d
if %errorlevel% neq 0 (
    echo [错误] Docker服务启动失败
    pause
    exit /b 1
)
echo      OK
echo.

:: 等待MySQL就绪
echo [2/4] 等待MySQL启动...
timeout /t 10 /nobreak >nul
echo      OK
echo.

:: 启动后端
echo [3/4] 启动后端服务...
cd /d "%~dp0backend"
start "KimiFiction-Backend" cmd /k "python -m uvicorn main:app --reload --port 8080"
echo      OK (http://localhost:8080)
echo.

:: 启动前端
echo [4/4] 启动前端服务...
cd /d "%~dp0frontend"
start "KimiFiction-Frontend" cmd /k "npm run dev"
echo      OK (http://localhost:5173)
echo.

:: 打开浏览器
echo 正在打开浏览器...
timeout /t 3 /nobreak >nul
start http://localhost:5173

echo ========================================
echo    启动完成！
echo ========================================
echo.
echo   后端API: http://localhost:8080
echo   API文档: http://localhost:8080/docs
echo   前端界面: http://localhost:5173
echo.
echo   Docker服务:
echo   - MySQL: localhost:3306
echo   - Redis: localhost:6379
echo   - Qdrant: localhost:6333
echo.
echo 关闭此窗口不会停止服务
echo 停止服务请运行: docker-compose down
echo ========================================
pause
