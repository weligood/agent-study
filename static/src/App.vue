<template>
  <div class="app-container">
    <AppHeader />
    <main class="main-content">
      <SearchCard @search="handleSearch" :loading="loading" />

      <!-- 推理步骤可视化（查询完成后可折叠） -->
      <ThinkingCard
        v-if="thinkingSteps.length"
        :steps="thinkingSteps"
        :isThinking="loading"
        :collapsed="!loading && !!result"
      />

      <!-- 查询结果 -->
      <ResultCard
        v-if="result"
        :result="result"
        @select-candidate="handleSelectCandidate"
        @follow-up="handleFollowUp"
      />

      <!-- 新对话按钮 -->
      <div v-if="result" class="session-actions">
        <button class="new-session-btn" @click="startNewSession">
          &#x1F504; 开始新对话
        </button>
      </div>
    </main>
    <AppFooter />
  </div>
</template>

<script>
const { ref, defineAsyncComponent } = Vue;
const { loadModule } = window['vue3-sfc-loader'];

const sfcOptions = {
  moduleCache: { vue: Vue },
  async getFile(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`加载失败: ${url}`);
    return res.text();
  },
  addStyle(css) {
    const el = document.createElement('style');
    el.textContent = css;
    document.head.appendChild(el);
  },
};

const load = (path) => defineAsyncComponent(() => loadModule(path, sfcOptions));

// 生成会话 ID
function generateSessionId() {
  return 'sess_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
}

function generateClientRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'req_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 10);
}

/** 将 API 错误 JSON（detail + request_id）拼成可读文案 */
function formatApiErrorBody(obj) {
  if (!obj || typeof obj !== 'object') return String(obj || '请求失败');
  const parts = [];
  if (obj.detail !== undefined && obj.detail !== null) {
    const d = obj.detail;
    parts.push(typeof d === 'string' ? d : JSON.stringify(d));
  }
  if (obj.request_id) parts.push('request_id: ' + obj.request_id);
  return parts.join(' · ') || '请求失败';
}

export default {
  name: 'App',
  components: {
    AppHeader:    load('/src/components/AppHeader.vue'),
    AppFooter:    load('/src/components/AppFooter.vue'),
    SearchCard:   load('/src/components/SearchCard.vue'),
    ResultCard:   load('/src/components/ResultCard.vue'),
    ThinkingCard: load('/src/components/ThinkingCard.vue'),
  },
  setup() {
    const result        = ref(null);
    const loading       = ref(false);
    const thinkingSteps = ref([]);
    const sessionId     = ref(generateSessionId());
    const lastPreferences = ref(null);

    const doSearch = async (params) => {
      const { queryType, query, hint } = params;
      if ('preferences' in params) {
        lastPreferences.value =
          params.preferences && Object.keys(params.preferences).length
            ? params.preferences
            : null;
      }
      loading.value       = true;
      result.value        = null;
      thinkingSteps.value = [];

      try {
        const payload = {
          query_type: queryType,
          hint: hint || null,
          session_id: sessionId.value,
        };
        if (queryType === 'title') payload.title = query;
        else payload.actor = query;
        if (lastPreferences.value && Object.keys(lastPreferences.value).length) {
          payload.preferences = lastPreferences.value;
        }

        const clientRequestId = generateClientRequestId();
        const jsonHeaders = {
          'Content-Type': 'application/json',
          'X-Request-ID': clientRequestId,
        };

        // 使用 SSE 流式端点
        const res = await fetch('/api/query/stream', {
          method: 'POST',
          headers: jsonHeaders,
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          let errBody = {};
          try {
            errBody = await res.json();
          } catch (_) {
            errBody = {};
          }
          throw new Error(formatApiErrorBody(errBody));
        }

        // 解析 SSE 事件流
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          let eventType = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              const dataStr = line.slice(6);
              try {
                const data = JSON.parse(dataStr);
                if (eventType === 'step') {
                  thinkingSteps.value.push(data);
                } else if (eventType.startsWith('trace.')) {
                  const sub = eventType.replace(/^trace\./, '');
                  const typeMap = {
                    start: 'start',
                    step: 'thinking',
                    tool_call: 'tool_call',
                    tool_result: 'tool_result',
                    human_needed: 'agent_action',
                    warning: 'error',
                    metrics: 'thinking',
                  };
                  const stepMsg =
                    sub === 'metrics' && data.payload && data.payload.metrics
                      ? `耗时 ${data.payload.metrics.total_ms} ms · ${data.payload.metrics.intent || ''} · ${data.payload.metrics.execution_mode || ''}`
                      : (data.message || eventType);
                  thinkingSteps.value.push({
                    type: typeMap[sub] || 'thinking',
                    message: stepMsg,
                    trace: data,
                    traceEvent: eventType,
                  });
                } else if (eventType === 'result.partial') {
                  result.value = data;
                } else if (eventType === 'result.final' || eventType === 'result') {
                  result.value = data;
                } else if (eventType === 'error') {
                  const em =
                    (data.message || '查询出错') +
                    (data.request_id ? ' · request_id: ' + data.request_id : '');
                  ElementPlus.ElMessage.error(em);
                  loading.value = false;
                }
              } catch (e) {
                // 忽略解析错误
              }
            }
          }
        }

        // 若 SSE 流没有返回 result（回退到非流式接口）
        if (!result.value) {
          const fallbackRes = await fetch('/api/query', {
            method: 'POST',
            headers: jsonHeaders,
            body: JSON.stringify(payload),
          });
          const fallbackData = await fallbackRes.json();
          if (fallbackRes.ok) {
            result.value = fallbackData;
          } else {
            throw new Error(formatApiErrorBody(fallbackData));
          }
        }
      } catch (err) {
        ElementPlus.ElMessage.error(err.message || '网络错误，请稍后重试');
      } finally {
        loading.value = false;
      }
    };

    const handleSearch = (params) => doSearch(params);

    const handleSelectCandidate = (candidate) =>
      doSearch({
        queryType: 'title',
        query: candidate.standard_title,
        hint: candidate.release_year
          ? String(candidate.release_year)
          : (candidate.work_id || ''),
      });

    // 追问处理：直接发送自然语言，由 Agent 的对话记忆理解上下文
    const handleFollowUp = (question) =>
      doSearch({
        queryType: 'title',
        query: question,
        hint: null,
      });

    const startNewSession = () => {
      sessionId.value     = generateSessionId();
      result.value        = null;
      thinkingSteps.value = [];
      ElementPlus.ElMessage.success('已开始新对话');
    };

    return {
      result,
      loading,
      thinkingSteps,
      handleSearch,
      handleSelectCandidate,
      handleFollowUp,
      startNewSession,
    };
  },
};
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, sans-serif;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  min-height: 100vh;
  color: #fff;
}

.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
  padding: 40px 20px;
}

.session-actions {
  margin-top: 20px;
  text-align: center;
}

.new-session-btn {
  padding: 10px 24px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  color: #ccc;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s;
}

.new-session-btn:hover {
  background: rgba(233, 69, 96, 0.15);
  border-color: #e94560;
  color: #e94560;
}
</style>
