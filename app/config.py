import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# 从项目根目录的 .env 文件加载环境变量
# Docker 环境下通过 volume 挂载宿主机的 .env，override=True 确保文件内容优先
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ========== 日志配置 ==========
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_level = getattr(logging, LOG_LEVEL, logging.INFO)
_root = logging.getLogger()
_root.setLevel(_level)
# uvicorn 启动后已存在 handler，直接调整级别和格式
for _handler in _root.handlers:
    _handler.setLevel(_level)
    # 如果 handler 还没有 formatter，设置一个
    if not _handler.formatter:
        _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
# 如果没有任何 handler（非 uvicorn 环境），添加默认 stdout handler
if not _root.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(_level)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    _root.addHandler(_handler)

APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "learn.db"

# ========== Ollama 配置 ==========
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
OLLAMA_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "180.0"))
OLLAMA_BATCH_SIZE = int(os.environ.get("OLLAMA_BATCH_SIZE", "40"))

# ========== OpenAI 兼容接口配置 ==========
# 释义来源：ollama（默认）或 openai
EXPLAINER_PROVIDER = os.environ.get("EXPLAINER_PROVIDER", "ollama").lower().strip()
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "").strip().rstrip("/")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "").strip()
OPENAI_TIMEOUT_SECONDS = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "180.0"))
OPENAI_BATCH_SIZE = int(os.environ.get("OPENAI_BATCH_SIZE", "40"))
