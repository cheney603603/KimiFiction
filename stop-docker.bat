@echo off
chcp 65001 >nul

cd /d D:\310Programm\KimiFiction

echo Stopping all services...
docker-compose down

echo.
echo All services stopped!
pause
