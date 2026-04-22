"""推荐与替代内容（助手层）：相似剧等，依赖资源层检索。"""

from tv_agent.recommendation.alternatives import (
    fetch_similar_envelope,
    similar_envelope_to_candidates,
)

__all__ = ["fetch_similar_envelope", "similar_envelope_to_candidates"]
