import os
from pathlib import Path

from dotenv import load_dotenv

# 从项目根目录的 .env 文件加载环境变量
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

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
