# 朗朗上口先读英语

本地单人英语预习 Web 应用。粘贴英文文章后，系统自动拆分段落、提取高频单词与短语、调用本地 Ollama 生成中文释义，并支持熟悉度标注、原文引用跳转、学习清单更新等完整学习闭环。

> **使用场景**：阅读英文文章前先扫清生词，带着理解进入原文，避免反复查词典打断阅读流。

---

## 核心功能

| 功能 | 说明 |
|---|---|
| 文章录入 | 粘贴英文文章，自动拆分为段落 |
| 词频分析 | 按出现频率排序提取单词和短语，词形还原（前后端共享规则 + irregular 映射表） |
| 中文释义 | 调用本地 Ollama 批量生成简洁中文解释 |
| 熟悉度标注 | 每个单词/短语可标记为：陌生 / 迷惑 / 熟悉 |
| 原文标注 | 可选下划线标注陌生词，支持自定义颜色配置 |
| 双击跳转 | 双击原文单词 → 跳转到词卡；5 秒内再次双击 → 跳转到单词本身含义 |
| 短语识别 | 基于常见短语模式识别（如 "skill for a"），优先跳转短语 |
| 引用面板 | 三栏布局，点击"查看引用"在右侧显示该词/短句在原文中的出现位置 |
| 熟悉度统计 | 文章顶部显示"量"和"唯一单词"两个维度的熟悉度百分比，悬停查看解释 |
| 历史文章 | 保存所有录入的文章和分析结果，支持重新分析更新学习清单 |

---

## 技术栈

- **后端**：Python 3.12 + FastAPI + SQLite + Jinja2
- **前端**：原生 JavaScript + HTMX + CSS（无框架依赖）
- **AI 释义**：Ollama（默认模型 `gemma4:e4b`）
- **部署**：Docker + docker-compose（可选）

---

## 快速开始

### 方式一：脚本启动（推荐）

**Windows**：
```powershell
.\start.bat
```

**Linux / macOS**：
```bash
chmod +x start.sh
./start.sh
```

脚本会自动创建虚拟环境、安装依赖、启动服务。

### 方式二：手动启动

```powershell
# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

访问 <http://127.0.0.1:8010>。

### 方式三：Docker

```bash
# 构建并启动
docker-compose up --build -d

# 停止
docker-compose down
```

数据持久化：`./data` 目录挂载到容器内。

---

## AI 释义配置（通过 `.env` 文件控制）

所有 AI 相关配置集中在项目根目录的 `.env` 文件中。已提供 `.env.copy` 作为配置模板。

### 快速配置

1. 复制模板：`cp .env.copy .env`（或手动创建 `.env`）
2. 按需修改 `.env` 中的值
3. 重启服务生效

### 可用环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `EXPLAINER_PROVIDER` | `ollama` | 释义来源：`ollama` 或 `openai` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 服务地址 |
| `OLLAMA_MODEL` | `gemma4:e4b` | Ollama 模型名 |
| `OLLAMA_TIMEOUT_SECONDS` | `180.0` | Ollama 请求超时（秒） |
| `OLLAMA_BATCH_SIZE` | `40` | Ollama 每批释义数量 |
| `OPENAI_BASE_URL` | `""` | OpenAI 兼容接口地址 |
| `OPENAI_API_KEY` | `""` | OpenAI 兼容接口 API Key |
| `OPENAI_MODEL` | `""` | OpenAI 兼容接口模型名 |
| `OPENAI_TIMEOUT_SECONDS` | `180.0` | OpenAI 请求超时（秒） |
| `OPENAI_BATCH_SIZE` | `40` | OpenAI 每批释义数量 |

### 切换到 OpenAI 兼容接口

在 `.env` 文件中修改：

```powershell
EXPLAINER_PROVIDER=openai
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o-mini
```

Docker 环境下 `.env` 文件会被自动映射进容器，无需额外修改 `docker-compose.yml`。

### 让 Ollama 接受外部连接

Ollama 默认只监听 `127.0.0.1`，Docker 容器无法直接访问。如使用 Docker + Ollama，需：

1. 将 `.env` 中的 `OLLAMA_BASE_URL` 改为 `http://host.docker.internal:11434`
2. 启动 Ollama 时监听所有接口：

**Windows**：
```powershell
$env:OLLAMA_HOST="0.0.0.0:11434"
ollama serve
```

**Linux / macOS**：
```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

如果 Ollama 不可用，文章分析仍会完成，释义显示为"待生成"。

---

## 项目结构

```
.
├── app/
│   ├── main.py              # FastAPI 路由和端点
│   ├── config.py            # 配置（支持环境变量）
│   ├── db.py                # SQLite 连接和 Schema
│   ├── templates/           # Jinja2 模板
│   │   ├── base.html
│   │   ├── index.html       # 文章录入 + 最近文章
│   │   ├── articles.html    # 历史文章列表
│   │   ├── article_detail.html  # 文章详情（三栏布局）
│   │   ├── terms.html       # 词库总览
│   │   └── _*.html          # 片段模板（引用、词卡、编辑器）
│   ├── static/
│   │   ├── app.js?v=12      # 前端逻辑（缓存版本号需递增）
│   │   └── styles.css       # 样式
│   └── services/
│       ├── analyzer.py      # 文本分析：分段、词形还原、短语识别
│       ├── analysis_store.py # 分析结果入库
│       └── ollama_client.py # Ollama 批量释义
├── tests/                   # pytest 测试（23 个）
├── data/
│   └── learn.db             # SQLite 数据库（自动创建）
├── start.bat / start.sh     # 一键启动脚本
├── Dockerfile               # Docker 构建
├── docker-compose.yml       # Docker 编排
└── requirements.txt
```

---

## 测试

```powershell
# 设置 PYTHONPATH 后运行
$env:PYTHONPATH="D:\Work\探索\朗朗上口先读英语"
pytest -q
```

23 个测试覆盖：文本分析、词形还原一致性、数据库操作、API 路由、单词定位逻辑。

---

## 关键注意事项

1. **缓存版本号**：`app.js` 和 `styles.css` 通过 `?v=N` 控制缓存，每次修改后需在 `base.html` 中递增版本号。
2. **文件编码**：项目文件统一使用 UTF-8，Windows PowerShell 输出可能出现乱码，写入文件时务必指定 `encoding='utf-8'`。
3. **时区显示**：数据库统一存储 UTC 时间，前端根据浏览器时区自动转换为本地时间。

---

## License

MIT
- **AI 释义**：Ollama（默认）或 OpenAI 兼容接口
│       └── ollama_client.py # Ollama / OpenAI 兼容释义客户端
