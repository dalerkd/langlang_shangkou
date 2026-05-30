#!/usr/bin/env bash
set -e

echo "============================================"
echo "  朗朗上口 - 启动服务"
echo "============================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

# Create venv if not exists
if [ ! -d ".venv" ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv .venv
fi

# Activate venv
echo "[2/4] 激活虚拟环境..."
source .venv/bin/activate

# Install deps
echo "[3/4] 安装依赖..."
pip install -q -r requirements.txt

# Ensure data dir
mkdir -p data

# Start server
echo "[4/4] 启动服务..."
echo ""
echo "访问地址: http://127.0.0.1:8010"
echo "按 Ctrl+C 停止服务"
echo ""

uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
