# AGENTS.md — 朗朗上口先读英语

> 面向后续 AI Agent 的项目上下文交接文档。接手本项目前请先通读本文。

---

## 1. 项目背景与目标

**朗朗上口先读英语**是一个本地单人英语预习 Web 应用。核心学习闭环：
1. 用户粘贴英文文章
2. 系统自动分段、提取高频单词/短语、词形还原
3. 调用本地 Ollama 生成中文释义
4. 用户预习词表（标记熟悉度：陌生/迷惑/熟悉）
5. 带着理解进入原文阅读，双击单词可跳转词卡/引用

**产品理念**：先清掉生词，再进入文章。界面简洁、功能实用、重视对齐和视觉细节。

---

## 2. 技术架构

| 层级 | 技术 | 说明 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI | REST API + Server-Side Rendering (Jinja2) |
| 数据库 | SQLite (`data/learn.db`) | 单文件数据库，自动创建 Schema |
| 前端 | 原生 JS + HTMX + CSS | 无 React/Vue 等框架，减少依赖 |
| AI 释义 | Ollama (`gemma4:e4b`) | 本地 LLM，批量生成中文解释 |
| 部署 | Docker / 本地脚本 | `start.bat` / `start.sh` / `docker-compose` |

### 关键文件映射

- `app/main.py` — 所有路由端点（首页、文章 CRUD、分析任务、引用、词库）
- `app/db.py` — SQLite 连接 + 5 张表的 Schema
- `app/config.py` — 全局配置，`OLLAMA_BASE_URL` 支持环境变量覆盖
- `app/services/analyzer.py` — 文本分析核心：分段、词频统计、词形还原、短语识别
- `app/services/analysis_store.py` — 分析结果持久化，触发 Ollama 释义
- `app/services/ollama_client.py` — Ollama HTTP 客户端，批量请求 JSON 格式释义
- `app/static/app.js` — 前端所有交互逻辑
- `app/static/styles.css` — 全部样式

---

## 3. 关键代码约定

### 3.1 缓存版本号（强制）
`app.js` 和 `styles.css` 在 `base.html` 中通过 `?v=N` 控制浏览器缓存。**每次修改这两个文件后，必须在 `base.html` 中递增 `N`**。当前版本：`?v=12`。

### 3.2 文件编码（强制）
项目文件存在 GBK/UTF-8 混用历史。**所有文件操作务必指定 `encoding='utf-8'`**。PowerShell 输出常显示乱码，但这不影响文件内容本身。

### 3.3 词形还原一致性（前后端必须同步）
前端 `app.js` 和后端 `app/services/analyzer.py` 中都有一个 `lemmatize_word` / `lemmatizeWord` 函数，**必须保持逻辑完全一致**。包括但不限于：
- 大小写转换规则
- irregular 映射表内容
- 通用规则（s/es/ed/ing 等后缀处理）

修改任一端后，必须同步另一端，并运行 `tests/test_lemmatize_consistency.py` 验证。

### 3.4 时间处理
- 数据库统一存储 UTC 时间（SQLite `CURRENT_TIMESTAMP`）
- 前端通过 `<time class="local-time" datetime="...">` + JS `formatLocalTime()` 自动转换为浏览器本地时区
- 后端 `_utc_now()` 使用 `datetime.now(timezone.utc).isoformat()`

---

## 4. 已知问题与限制

### 4.1 Docker 访问宿主机 Ollama
- Docker 容器内 `localhost` / `127.0.0.1` 指向容器自身，不是宿主机
- 已配置 `OLLAMA_BASE_URL=http://host.docker.internal:11434` + `extra_hosts`
- **但 Ollama 默认只监听 `127.0.0.1`**，需手动设置 `OLLAMA_HOST=0.0.0.0:11434` 才能接受容器连接
- 如果无法修改 Ollama 监听地址，可将 `OLLAMA_BASE_URL` 改为宿主机真实局域网 IP

### 4.2 SQLite 时区
- `CURRENT_TIMESTAMP` 返回 UTC，但字符串格式不带 `Z` 后缀
- 前端 JS 解析时手动补 `Z`：`utcString.replace(' ', 'T') + 'Z'`

### 4.3 词形还原覆盖范围
- irregular 映射表已补全常见动词的过去式/过去分词/现在分词，但不可能穷尽所有英语不规则变化
- 未覆盖的单词会被规则还原（可能不准确）

---

## 5. 用户偏好与工作方式

这是从大量交互中总结出的用户偏好，后续修改请严格遵守：

1. **界面简洁，功能实用** — 不堆功能，每个功能都要有明确的学习价值
2. **重视对齐和视觉细节** — 滚动位置、标题栏对齐、元素间距都要精确调整
3. **鼠标悬停提示** — 复杂指标（如熟悉度统计）必须有 `title` 属性解释含义
4. **跨平台支持** — Windows / Linux / macOS 都要能运行
5. **Sticky 置顶** — 重要操作栏/标题栏需要 `position: sticky` 保持可见
6. **双击交互** — 双击原文单词是核心交互，需精确匹配上下文位置（不是全文第一个匹配）
7. **短语优先** — 双击时先判断是否为短语，短语优先跳转；5 秒内再次双击才跳转到单词本身
8. **记忆用户选择** — 开关/配置需要持久化用户偏好（localStorage 或后端存储）

---

## 6. 历史关键决策记录

| 时间 | 决策 | 原因 |
|---|---|---|
| 早期 | 前后端共享词形还原规则 | 保证双击定位和后端统计的一致性 |
| 早期 | 三栏布局（原文 / 词表 / 引用） | 用户要求引用面板放右侧，点击其他区域隐藏 |
| 中期 | 短语识别基于常见模式 + 上下文位置匹配 | 避免 "skill for a" 中的 `for` 被错误匹配为 `format for` |
| 中期 | `user_edited` 字段标记人工修订的释义 | 防止"更新学习清单"覆盖用户手动修改的内容 |
| 中期 | 熟悉度统计分"量"和"唯一单词"两个维度 | "量"考量重复出现后的非陌生占比，"唯一单词"仅计算去重后的比例 |
| 近期 | 前端时区转换（而非后端） | 自适应任何用户的浏览器时区，无需后端感知用户位置 |
| 近期 | Docker 支持 + 启动脚本 | 用户需要跨平台一键启动和容器化部署 |

---

## 7. 测试

运行方式：

```
$env:PYTHONPATH="D:\Work\探索\朗朗上口先读英语"
pytest -q
```

23 个测试，覆盖：
- `test_analyzer.py` — 文本分析、分段、词频统计
- `test_app.py` — API 路由、表单提交、页面渲染
- `test_db.py` — 数据库 Schema、外键约束
- `test_lemmatize_consistency.py` — 前后端词形还原一致性（关键）
- `test_locate.py` — 单词定位、短语匹配逻辑

**修改后必须运行 pytest 验证无回归。**

---

## 8. 后续改进方向（非紧急）

以下方向来自用户历史交互中的隐含需求，可供参考：

- [ ] 更多 irregular 动词补全
- [ ] 短语识别算法扩展（更丰富的短语模式）
- [ ] 用户配置持久化后端化（当前部分在 localStorage）
- [ ] 导入/导出学习数据
- [ ] 文章分类/标签
- [ ] 学习进度统计（跨文章维度）
- [ ] 支持非 Ollama 的释义来源（如 OpenAI API）

---

## 9. 交接检查清单

接手项目时，请确认：

- [ ] 通读本文件
- [ ] `pytest` 23 个测试全部通过
- [ ] `node -c app/static/app.js` 语法检查通过
- [ ] 修改 `app.js`/`styles.css` 后递增 `base.html` 中的 `?v=N`
- [ ] 所有文件写入指定 `encoding='utf-8'`
- [ ] 修改词形还原后同步前后端并运行 `test_lemmatize_consistency.py`

---

## 10. 联系方式

本项目为个人学习工具，如有问题请通过原始对话线程沟通。
| AI 释义 | Ollama（默认）或 OpenAI 兼容接口 | 通过 `EXPLAINER_PROVIDER` 切换 |
- `app/services/ollama_client.py` — Ollama / OpenAI 兼容释义客户端
- Docker 使用 Ollama 时：`localhost` / `127.0.0.1` 指向容器自身
- Docker 使用 OpenAI 兼容接口时：无需此限制，直接访问外部 API 即可
| 近期 | 支持 OpenAI 兼容接口 | 用户需要非 Ollama 的释义来源，通过 `EXPLAINER_PROVIDER` 切换 |
- [x] 支持非 Ollama 的释义来源（如 OpenAI API）
- `app/.env` — 所有动态配置的集中控制点（AI 来源、模型参数等）
### 3.5 环境变量配置（通过 `.env` 文件）

所有动态控制项统一放在项目根目录 `.env` 文件中，`app/config.py` 通过 `python-dotenv` 自动加载：

- `EXPLAINER_PROVIDER` — 切换释义来源（`ollama` / `openai`）
- `OLLAMA_*` — Ollama 的连接地址、模型、超时、批次大小
- `OPENAI_*` — OpenAI 兼容接口的地址、Key、模型、超时、批次大小

`.env.copy` 是配置模板，`.env` 被 `.gitignore` 忽略。修改 `.env` 后重启服务生效。
| 近期 | `.env` 集中配置 | 用户需要方便地切换 AI 来源和模型参数，Docker 自动映射 |
