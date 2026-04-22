"""
电视剧正版查询领域包（与 FastAPI `app` 解耦）。

推荐目录心智模型：
- `domain/` — 领域模型与 DTO（`schemas`）
- `graphs/` — LangGraph 编排
- `agent/`、`pipeline.py` — Agent 插件与确定性流水线入口
- `tools/` — `internal/`（图节点直连检索）、`agent_tools/`（@tool 与注册表）
- `orchestrator/` — 意图与执行模式决策
- `policy/` — 下载/来源/LLM 护栏
- `resources/` — 平台目录、地区与别名等静态知识
- `config/` — 从 Settings 投影的分层配置视图
- `search/` — 搜索后端与解析
- `resolution/` — 标题规范化与消歧
- `availability/` — StreamingOffer 映射与排序
- `preferences/` — 用户偏好过滤
- `recommendation/` — 相似与替代内容
- `trace/` — TraceEvent、SSE、LangChain 回调
- `download/` — 受控下载任务
"""

from tv_agent.agent import build_executor, parse_agent_output_to_result, run_availability_query
from tv_agent.domain.schemas import TVAvailabilityResult

__all__ = [
    "TVAvailabilityResult",
    "build_executor",
    "parse_agent_output_to_result",
    "run_availability_query",
]
__version__ = "0.4.0"
