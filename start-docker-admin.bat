@echo off
chcp 65001 >nul
echo.
echo ==========================================
echo    NovelGen Docker 启动脚本（管理员）
echo ==========================================
echo.

cd /d D:\310Programm\KimiFiction

echo [1/4] 启动基础设施（Redis + Qdrant + MySQL）...
docker-compose up -d redis qdrant mysql

echo.
echo [2/4] 等待数据库初始化（15秒）...
timeout /t 15 /nobreak >nul

echo.
echo [3/4] 启动后端服务...
docker-compose up -d backend

echo.
echo [4/4] 启动前端服务...
docker-compose up -d frontend

echo.
echo ==========================================
echo    服务启动完成！
echo ==========================================
echo.
echo 访问地址：
echo   前端界面: http://localhost:5173
echo   API文档:  http://localhost:8000/docs
echo.
echo 查看日志: docker-compose logs -f
echo 停止服务: docker-compose down
echo.
pause
