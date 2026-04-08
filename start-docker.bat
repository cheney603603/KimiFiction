@echo off
chcp 65001 >nul

cd /d D:\310Programm\KimiFiction

echo [1/4] Starting infrastructure (Redis + Qdrant + MySQL)...
docker-compose up -d redis qdrant mysql

echo.
echo [2/4] Waiting for database init (15s)...
timeout /t 15 /nobreak >nul

echo.
echo [3/4] Starting backend...
docker-compose up -d backend

echo.
echo [4/4] Starting frontend...
docker-compose up -d frontend

echo.
echo ==========================================
echo    Services Started!
echo ==========================================
echo.
echo Access:
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo.
echo Logs: docker-compose logs -f
echo Stop:  docker-compose down
echo.
pause
