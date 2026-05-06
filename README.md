# Pivot AI Assistant

Pivot AI Assistant 是一个前后端分离的个人智能助手项目，面向本地知识库问答、联网信息检索、工具调用和会话管理等场景。项目后端使用 FastAPI 提供 API 服务与 Agent 编排能力，前端使用 Vue 3、Vite 和 Element Plus 构建聊天工作台与知识库管理界面。

> 当前项目适合作为个人 AI 助手、RAG 知识库问答系统或多工具 Agent 原型进行扩展。

## 功能特性

- **多会话聊天**：支持创建、切换、删除会话，并持久化保存历史消息。
- **流式 AI 回复**：前端通过 `fetch` 读取后端 `/api/chat/stream` 的流式响应，提升聊天体验。
- **本地知识库**：支持上传 `txt`、`md`、`pdf`、`docx`、`csv`、`xlsx`、`xls` 文件，提取文本后切分为知识片段。
- **RAG 检索增强**：后端通过 ChromaDB 保存向量数据，并在不可用时回退到本地 JSON 向量存储。
- **Embedding 回退机制**：优先调用 DashScope 兼容 OpenAI 的 Embedding 接口，失败时使用本地哈希向量作为降级方案。
- **大模型接入**：通过 DashScope OpenAI-compatible API 调用通义千问模型，默认模型为 `qwen-max`。
- **工具调用**：预留并实现 Tavily 搜索、天气、时间、定位、Bilibili 热门视频抓取等工具能力。
- **前端知识库管理**：提供文件暂存、批量上传、知识库统计、向量数量展示和文件删除功能。
- **语音输入入口**：前端包含 `VoiceInput` 组件，可作为浏览器语音输入能力的扩展入口。

## 技术栈

### 后端

- Python
- FastAPI
- Uvicorn
- Pydantic Settings
- SQLite / aiosqlite
- ChromaDB
- LangChain / LangGraph
- httpx
- python-docx
- pypdf
- openpyxl

### 前端

- Vue 3
- Vite
- Vue Router
- Element Plus
- Axios
- `@element-plus/icons-vue`

### 外部服务

- DashScope OpenAI-compatible API
- Tavily Search API
- 高德天气 API
- Bilibili 热门视频接口

## 项目结构

```text
Pivot_AI_Assistant/
├── backend/
│   ├── app/
│   │   ├── agents/        # Agent 编排、意图识别、RAG、工具调用、回答校验
│   │   ├── db/            # SQLite 会话与知识库元数据
│   │   ├── models/        # Pydantic 请求与响应模型
│   │   ├── rag/           # 文档切分、Embedding、检索、向量存储
│   │   ├── routers/       # Chat 与 Knowledge API 路由
│   │   ├── services/      # LLM 客户端
│   │   ├── tools/         # 搜索、天气、时间、定位、爬虫等工具
│   │   ├── utils/         # 文件解析、MD5 等工具函数
│   │   ├── config.py      # 环境变量与运行配置
│   │   └── main.py        # FastAPI 应用入口
│   ├── .env.example       # 后端环境变量示例
│   └── requirements.txt   # Python 依赖
├── frontend/
│   ├── src/
│   │   ├── api/           # 前端 API 封装
│   │   ├── components/    # 聊天消息、会话列表、语音输入组件
│   │   ├── router/        # Vue Router 配置
│   │   ├── views/         # 聊天页与知识库页
│   │   ├── App.vue        # 应用布局
│   │   └── main.js        # 前端入口
│   ├── package.json       # 前端依赖与脚本
│   └── vite.config.js     # Vite 配置
├── .gitignore
└── README.md
```

## 环境变量

后端读取 `backend/.env`，可参考 `backend/.env.example` 创建本地配置。

```env
DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
TAVILY_API_KEY=your_tavily_api_key
TAVILY_BASE_URL=https://api.tavily.com
AMAP_WEATHER_API_KEY=your_amap_weather_api_key
AMAP_WEATHER_BASE_URL=https://restapi.amap.com/v3/weather/weatherInfo
AMAP_ADCODE_PATH=./app/data/AMap_adcode_citycode.xlsx
QWEN_MODEL=qwen-max
EMBEDDING_MODEL=text-embedding-v4
DATABASE_URL=sqlite:///./app/data/pivot_ai.db
UPLOAD_DIR=./app/data/uploads
CHROMA_DIR=./app/data/chroma
CRAWLER_CACHE_DIR=./app/data/cache
CRAWLER_CACHE_TTL_SECONDS=3600
FRONTEND_ORIGIN=http://localhost:5173
RAG_COLLECTION_NAME=pivot_ai_knowledge
CHUNK_SIZE=600
CHUNK_OVERLAP=80
EMBEDDING_DIMENSIONS=1024
RETRIEVAL_TOP_K=5
```

前端默认请求 `http://127.0.0.1:8000`，可在 `frontend/.env` 中覆盖：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 本地启动

### 1. 启动后端

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

后端健康检查：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok"}
```

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

```text
http://localhost:5173
```

## API 概览

### 健康检查

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 检查后端服务状态 |

### 会话与聊天

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/sessions` | 获取会话列表 |
| `POST` | `/api/sessions` | 创建会话 |
| `DELETE` | `/api/sessions/{session_id}` | 删除会话 |
| `GET` | `/api/sessions/{session_id}/messages` | 获取会话消息 |
| `POST` | `/api/chat` | 普通聊天响应 |
| `POST` | `/api/chat/stream` | 流式聊天响应 |

### 知识库

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/knowledge/files` | 获取知识库文件统计 |
| `POST` | `/api/knowledge/upload` | 上传文件并写入向量库 |
| `POST` | `/api/knowledge/confirm` | 知识库确认占位接口 |
| `DELETE` | `/api/knowledge/files/{file_id}` | 删除知识库文件与向量 |

## Agent 工作流程

```text
用户输入
  ↓
intent_agent 判断意图
  ↓
task 类型请求触发 RAG 检索与工具调用
  ↓
generation_agent 组合历史消息、知识片段和工具结果
  ↓
llm_client 调用 DashScope Chat Completions
  ↓
verification_agent 校验回答
  ↓
返回普通响应或流式响应
```

当大模型服务或 Embedding 服务不可用时，项目包含本地降级逻辑，可返回基础整理结果或使用本地哈希向量完成检索原型验证。

## 知识库处理流程

```text
上传文件
  ↓
校验文件类型
  ↓
保存到 backend/app/data/uploads
  ↓
按文件类型提取文本
  ↓
切分 chunk
  ↓
生成 Embedding
  ↓
写入 ChromaDB
  ↓
保存 SQLite 元数据
```

支持的文件类型包括：

- `txt`
- `md`
- `pdf`
- `docx`
- `csv`
- `xlsx`
- `xls`

## 数据与缓存

项目运行时会在 `backend/app/data/` 下生成本地数据：

- `pivot_ai.db`：SQLite 主数据库
- `uploads/`：上传文件目录
- `chroma/`：ChromaDB 向量库目录
- `cache/`：爬虫缓存目录

这些运行数据已在 `.gitignore` 中忽略，上传 GitHub 时通常不需要提交。

## 上传 GitHub 前建议

- 不要提交 `backend/.env`、`frontend/.env`、API Key、数据库文件、上传文件和缓存文件。
- 保留 `backend/.env.example`，方便其他开发者快速了解需要配置哪些变量。
- `frontend/node_modules/`、`frontend/dist/`、`backend/.venv/`、`backend/app/data/` 已在 `.gitignore` 中忽略。
- 如需公开展示项目，建议补充截图、演示 GIF 或部署说明。
- 当前部分前端与后端中文文案在源码中存在编码显示异常，README 已使用正常 UTF-8 中文重写；后续如要正式发布，建议单独修复源码文案编码。

## 常见问题

### 1. 没有配置 DashScope API Key 可以运行吗？

可以运行基础服务，但真实大模型回答和远程 Embedding 会失败。项目内置了降级逻辑：聊天会返回本地整理结果，Embedding 会回退到本地哈希向量，适合进行流程验证。

### 2. 上传文件后向量库在哪里？

默认保存在：

```text
backend/app/data/chroma
```

如果 ChromaDB 写入失败，会回退保存到：

```text
backend/app/data/chroma/fallback_vectors.json
```

### 3. 前端请求后端失败怎么办？

确认后端已启动在 `http://127.0.0.1:8000`，并检查：

- `backend/.env` 中的 `FRONTEND_ORIGIN`
- `frontend/.env` 中的 `VITE_API_BASE_URL`
- 浏览器控制台是否存在 CORS 或网络错误

### 4. Bilibili、天气或联网搜索没有结果怎么办？

检查对应 API Key、网络访问能力和环境变量配置。Tavily 搜索和高德天气依赖外部服务，Bilibili 热门视频抓取依赖公开接口可访问性。

## 开发状态

当前项目已经具备完整的本地运行骨架：

- 后端 API 服务已搭建
- 前端聊天与知识库页面已搭建
- 会话、消息、知识库元数据支持 SQLite 持久化
- RAG、工具调用、LLM 客户端和降级方案已具备基础实现

后续可继续完善源码中文编码、增加测试用例、补充鉴权、优化工具调用策略，并添加部署配置。
