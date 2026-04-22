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

    const doSearch = async ({ queryType, query, hint }) => {
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

        // 使用 SSE 流式端点
        const res = await fetch('/api/query/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || '查询失败');
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
                } else if (eventType === 'result') {
                  result.value = data;
                } else if (eventType === 'error') {
                  ElementPlus.ElMessage.error(data.message || '查询出错');
                  loading.value = false;  // error 时立即停止 loading
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
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          const fallbackData = await fallbackRes.json();
          if (fallbackRes.ok) {
            result.value = fallbackData;
          } else {
            throw new Error(fallbackData.detail || '查询失败');
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
