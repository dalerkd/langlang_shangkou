@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   朗朗上口 - 启动服务
echo ============================================

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [1/4] 创建虚拟环境...
    python -m venv .venv
)

echo [2/4] 激活虚拟环境...
call .venv\Scripts\activate.bat

echo [3/4] 安装依赖...
pip install -q -r requirements.txt

if not exist "data" mkdir data

echo [4/4] 启动服务...
echo.
echo 访问地址: http://127.0.0.1:8010
echo 按 Ctrl+C 停止服务
echo.

uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload

pause
