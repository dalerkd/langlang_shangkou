@echo off
setlocal EnableDelayedExpansion

if "%~1"=="" (
    call :help
    exit /b 1
)

call :%~1 2>nul
if errorlevel 1 (
    echo Unknown command: %~1
    call :help
    exit /b 1
)
exit /b 0

:build
echo [build] Building image...
docker compose build
exit /b 0

:up
echo [up] Starting services...
docker compose up -d
echo.
echo Service started at http://localhost:8010
exit /b 0

:down
echo [down] Stopping services...
docker compose down
exit /b 0

:logs
echo [logs] Following logs...
docker compose logs -f web
exit /b 0

:rebuild
echo [rebuild] Rebuilding and restarting service...
call :down
call :build
call :up
exit /b 0

:pull
echo [pull] Pulling latest image and restarting...
docker compose pull
docker compose up -d
exit /b 0

:help
echo Usage: build.bat [command]
echo.
echo Commands:
echo   build    Build Docker image
echo   up       Start services in background
echo   down     Stop and remove containers
echo   logs     Follow logs
echo   rebuild  Stop, build, and start service
echo   pull     Pull latest image and restart
echo.
echo Example: build.bat build ^& build.bat up
exit /b 0
