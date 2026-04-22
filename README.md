# TV Legal Availability Agent

基于 **Python + LangChain** 的「电视剧正版平台查询」智能体项目：支持 **SSE 推理可视化**、**多轮对话记忆**、**演员查询** 与 **相似剧推荐**，由 Tool Calling Agent 编排调用工具链，输出 Pydantic 校验过的结构化 JSON。

## 核心特性

- **SSE 流式推理可视化**：前端实时展示 AI 推理步骤（工具调用、思考过程）
- **多轮对话记忆**：基于 session 的 ConversationBufferWindowMemory，支持追问
- **四大工具**：剧集元数据查询、正版平台查询、演员作品查询、相似剧推荐
- **15+ 部模拟剧集**：覆盖多平台、多演员的丰富 mock 数据
- **Vue 3 + Element Plus 前端**：暗色主题，推理动画，平台 Logo + 跳转

## 合规声明（必读）

本仓库仅演示**如何组织查询流程与输出结构**，内置数据为**离线模拟**，不代表任何实时版权状态。你必须：

- 不在输出中提供盗版、磁力/BT、破解或绕过 DRM/地区限制/付费墙的方法；
- 不对未经验证的来源做「已证实」陈述；
- 生产环境对接 **TMDB / JustWatch / 平台开放数据** 等合规数据源，并完成法务审核。

## 目录结构

```text
.
├── app/                       # FastAPI：Web、配置、API 入参、服务编排
│   ├── main.py
│   ├── api/
│   │   ├── router.py
│   │   └── routes/tv.py       # /api/query + /api/query/stream (SSE)
│   ├── core/                  # pydantic-settings、日志
│   ├── schemas/               # HTTP 层入参（TvQueryRequest + session_id）
│   └── services/              # 异步封装 Agent 调用 + SSE 流生成器
├── tv_agent/                  # 领域包：与 Web 解耦，可单独测试/复用
│   ├── agent.py               # LangChain AgentExecutor（支持 memory/callbacks）
│   ├── tools.py               # 4 个工具：metadata/platforms/actor/similar
│   ├── prompt.py              # System Prompt + chat_history 占位符
│   ├── mock_data.py           # 15+ 部剧、14 位演员、相似剧映射
│   ├── schemas.py             # TVAvailabilityResult / PlatformInfo(logo_url)
│   ├── callbacks.py           # SSE StreamingStepHandler 回调
│   └── memory.py              # SessionStore 对话记忆管理
├── static/                    # Vue 3 前端（无构建工具，CDN + vue3-sfc-loader）
│   ├── index.html
│   └── src/components/        # App / SearchCard / ResultCard / ThinkingCard
├── api.py                     # uvicorn 兼容入口 → app.main:app
├── main.py                    # python main.py → 启动 uvicorn
├── config.py                  # 再导出 app.core.config（供 tv_agent 读配置）
├── requirements.txt
├── .env.example
└── tests/
    └── test_tools.py
```

## 模块职责与数据流

1. **`app/main.py`（Web）**：`create_app()`、`lifespan`、CORS、静态文件、`/api`。
2. **`tv_agent/`**：LangChain Agent、工具、Prompt、领域模型、回调、记忆；**不依赖** `app`。
3. **`app/services/tv_service.py`**：
   - `query_tv()` — 非流式调用
   - `stream_tv_query()` — SSE 异步生成器（推理步骤 + 结果）
4. **`tv_agent/callbacks.py`**：`StreamingStepHandler` 将 Agent 事件推送到 `asyncio.Queue`。
5. **`tv_agent/memory.py`**：`SessionStore` 管理多会话记忆，自动过期清理（TTL 30 分钟）。

数据流（SSE）：`HTTP POST → StreamingResponse → Agent(回调→Queue) → SSE events → 前端`。

## 安装

1. Python 3.10+。
2. `pip install -r requirements.txt`
3. `copy .env.example .env`，填写 `OPENAI_API_KEY` 等。

## 环境变量

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | OpenAI 或兼容 API Key（必填） |
| `OPENAI_BASE_URL` | 可选网关 |
| `MODEL_NAME` | 默认 `gpt-4o-mini` |
| `SEARCH_API_KEY` / `SEARCH_BASE_URL` | 可选远程检索 |
| `REQUEST_TIMEOUT_SECONDS` | 超时（秒） |
| `AGENT_MAX_ITERATIONS` | Agent 最大迭代 |
| `LOG_LEVEL` | 日志级别 |
| `CORS_ORIGINS` | `*` 或逗号分隔来源 |

配置由 **pydantic-settings** 从仓库根 `.env` 加载（见 `app/core/config.py`）。

## 运行

```bash
# 启动 Web 服务（推荐）
python main.py
# 或
uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

浏览器：**http://127.0.0.1:8765/** ，API 文档：**http://127.0.0.1:8765/docs**。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/query` | 非流式查询，返回 JSON |
| POST | `/api/query/stream` | SSE 流式查询，实时推理步骤 + 结果 |

## 模拟数据

15+ 部剧：狂飙、Breaking Bad、平凡的世界、人民的名义、琅琊榜、甄嬛传、庆余年、三体、长安十二时辰、知否知否、觉醒年代、繁花、隐秘的角落、漫长的季节等。

14 位演员映射：张译、张颂文、胡歌、孙俪、张若昀、秦昊、雷佳音等。

## 远程接口替换（SEARCH_BASE_URL）

由 `tv_agent/tools.py` 发起：

- `GET {SEARCH_BASE_URL}/tv/metadata?...`
- `GET {SEARCH_BASE_URL}/tv/platforms?...`

响应 envelope 与 mock 一致；演进字段时请同步 `tv_agent/schemas.py` 与 `tv_agent/prompt.py`。

## 测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## 许可证与责任

示例代码仅供学习；对外服务前请自行完成版权与合规评估。
