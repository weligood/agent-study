# TV Legal Availability Agent

基于 **Python + LangChain** 的「电视剧正版平台查询」项目：默认走 **确定性检索流水线**（快、结构化稳定）；可选 **Tool Calling Agent** 用于 **视频 URL 解析/下载** 与复杂多轮追问。支持 **SSE 步骤事件**、**会话记忆**（agent 模式）、**演员查询** 与 **相似剧推荐**，输出经 Pydantic 校验的结构化 JSON。

## 核心特性

- **SSE 流式推理可视化**：前端实时展示 AI 推理步骤（工具调用、思考过程）
- **多轮对话记忆**：基于 session 的 ConversationBufferWindowMemory，支持追问
- **检索流水线**（`tv_agent/pipeline.py`）：元数据 → 平台 → 相似剧，不经由 LLM 编排
- **工具链**：**SearXNG** 元搜索（自托管）+ DuckDuckGo 回退 + 可选 LangChain 工具（含视频信息提取）
- **视频提取 LangGraph**（`video_scraper/extract_graph.py`）：按 URL 分类后**只进入对应平台**提取节点，不依次尝试全部爬虫
- **Vue 3 + Element Plus 前端**：暗色主题，推理动画，平台 Logo + 跳转

## 合规声明（必读）

本仓库演示**查询流程与输出结构**；数据来自 SearXNG / DuckDuckGo 等联网检索，不代表任何实时版权状态。你必须：

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
│   ├── llm_client.py          # ChatOpenAI / Agent Runnable / 结构化抽取链缓存
│   ├── agent.py               # AgentExecutor；JSON 解析失败时用 with_structured_output 兜底
│   ├── pipeline.py            # 确定性剧名/演员检索链（默认路径）
│   ├── search/                # 联网搜索（SearXNG 优先 + DuckDuckGo 回退 + 可选 Meili 融合）
│   ├── tools.py               # 搜索与视频相关 LangChain 工具
│   ├── prompt.py              # System Prompt + chat_history 占位符
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
    ├── test_tools.py
    ├── test_pipeline.py
    ├── test_agent_output.py
    ├── test_video_extract_graph.py
    ├── test_search_backends.py
    └── test_searxng_parse.py
```

## 模块职责与数据流

1. **`app/main.py`（Web）**：`create_app()`、`lifespan`、CORS、静态文件、`/api`。
2. **`tv_agent/`**：`pipeline`（默认）、LangChain Agent、工具、Prompt、领域模型、回调、记忆；**不依赖** `app`。
3. **`app/services/tv_service.py`**：按 `TV_QUERY_MODE` 与输入类型选择流水线或 Agent；`stream_tv_query()` 为 SSE。
4. **`tv_agent/callbacks.py`**：`StreamingStepHandler` 将 Agent 事件推送到 `asyncio.Queue`（仅 agent 模式有工具步骤流）。
5. **`tv_agent/memory.py`**：`SessionStore` 管理多会话记忆（agent 模式），TTL 可配置。

数据流（SSE，pipeline）：`HTTP POST → StreamingResponse → 线程池执行 pipeline → SSE(step+result) → 前端`。

数据流（SSE，agent）：`HTTP POST → StreamingResponse → Agent(回调→Queue) → SSE events → 前端`。

## 安装

1. Python 3.10+。
2. `pip install -r requirements.txt`
3. `copy .env.example .env`：填写 `SEARXNG_BASE_URL` 可走自建元搜索；不配则默认走 DuckDuckGo 回退（无 Key）；agent 或视频 URL 需 `OPENAI_API_KEY`。

## 环境变量

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | OpenAI 或兼容 API Key（`TV_QUERY_MODE=agent` 或视频 URL 查询时必填） |
| `OPENAI_BASE_URL` | 可选网关 |
| `MODEL_NAME` | 默认 `gpt-4o-mini`（Agent 主模型） |
| `EXTRACTOR_MODEL_NAME` | 可选；结构化抽取用，未设则同主模型 |
| `OPENAI_MAX_RETRIES` | 可重试错误时的最大重试次数，默认 `2` |
| `AGENT_PARALLEL_TOOL_CALLS` | 默认 `true`；网关报错时可 `false` |
| `SEARXNG_BASE_URL` | 自托管 [SearXNG](https://github.com/searxng/searxng) 根 URL（不配则仅用 DuckDuckGo） |
| `SEARCH_FALLBACK_DDG` | SearXNG 未配置、失败或无结果时是否回退 DuckDuckGo，默认 `true` |
| `MEILISEARCH_URL` / `MEILISEARCH_API_KEY` / `MEILISEARCH_INDEX` | 可选；配置后启用片库与联网融合 |
| `REQUEST_TIMEOUT_SECONDS` | 超时（秒） |
| `AGENT_MAX_ITERATIONS` | Agent 最大迭代 |
| `TV_QUERY_MODE` | `pipeline`（默认）或 `agent`；视频 URL 输入会强制 agent |
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

## 联网搜索

实现见 `tv_agent/search/backends.py`：**仅** SearXNG 与 DuckDuckGo（不再使用付费 SearchAPI）；统一为 `organic_results` / `knowledge_graph`，供 `tv_agent/tools.py` 解析。

| 思路来源（GitHub） | 说明 |
|-------------------|------|
| [searxng/searxng](https://github.com/searxng/searxng) | 元搜索、自托管；本仓库用其 JSON API（`format=json`），解析见 `tv_agent/search/searxng_parse.py`（infoboxes / answers / results 等） |
| [deedy5/duckduckgo_search](https://github.com/deedy5/duckduckgo_search) | 无 API Key 的文本检索，适合开发与轻量场景 |
| [meilisearch/meilisearch](https://github.com/meilisearch/meilisearch) | 可选自建剧名片库；`MEILISEARCH_URL` 配置后命中会**前置**与联网 `organic_results` 融合（`tv_agent/search/meili_fusion.py`），示例入库：`python scripts/meili_seed_tv_titles.py` |

演进字段时请同步 `tv_agent/schemas.py` 与 `tv_agent/prompt.py`。

## 测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## 许可证与责任

示例代码仅供学习；对外服务前请自行完成版权与合规评估。
