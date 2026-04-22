<template>
  <div class="thinking-card" v-if="steps.length > 0">
    <div class="thinking-header" @click="toggleCollapse" :class="{ clickable: canCollapse }">
      <span class="thinking-icon">&#x1F9E0;</span>
      <span class="thinking-title">AI 推理过程</span>
      <span v-if="isThinking" class="thinking-pulse"></span>
      <span v-if="canCollapse" class="collapse-icon">{{ isCollapsed ? '▶' : '▼' }}</span>
    </div>
    <div class="thinking-steps" v-show="!isCollapsed">
      <div
        v-for="(step, index) in steps"
        :key="index"
        class="thinking-step"
        :class="[step.type, step.traceEvent ? 'has-trace' : '']"
      >
        <div class="step-main">
          <span class="step-icon">{{ getStepIcon(step.type) }}</span>
          <span class="step-message">{{ step.message }}</span>
          <span v-if="step.traceEvent" class="event-badge">{{ step.traceEvent }}</span>
        </div>
        <div v-if="formatStepMeta(step)" class="step-meta">{{ formatStepMeta(step) }}</div>
        <details v-if="step.trace && step.trace.payload && step.trace.payload.nodes" class="step-details">
          <summary>LangGraph 节点 ({{ step.trace.payload.nodes.length }})</summary>
          <ol class="node-list">
            <li v-for="(n, i) in step.trace.payload.nodes" :key="i">{{ n }}</li>
          </ol>
        </details>
      </div>
    </div>
  </div>
</template>

<script>
const { ref, watch } = Vue;

export default {
  name: 'ThinkingCard',
  props: {
    steps: {
      type: Array,
      default: () => [],
    },
    isThinking: {
      type: Boolean,
      default: false,
    },
    collapsed: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const isCollapsed = ref(false);
    const canCollapse = ref(false);

    // 查询完成后自动折叠
    watch(() => props.collapsed, (val) => {
      canCollapse.value = val;
      if (val) isCollapsed.value = true;
    });

    // 开始新查询时自动展开
    watch(() => props.isThinking, (val) => {
      if (val) {
        isCollapsed.value = false;
        canCollapse.value = false;
      }
    });

    const toggleCollapse = () => {
      if (canCollapse.value) {
        isCollapsed.value = !isCollapsed.value;
      }
    };

    const getStepIcon = (type) => {
      const icons = {
        start: '\u{1F680}',
        thinking: '\u{1F4AD}',
        tool_call: '\u{1F527}',
        tool_result: '\u{1F4E6}',
        agent_action: '\u{2699}\u{FE0F}',
        agent_finish: '\u{2705}',
        error: '\u{274C}',
      };
      return icons[type] || '\u{1F4CC}';
    };

    const formatStepMeta = (step) => {
      const t = step.trace;
      if (!t || typeof t !== 'object') return '';
      const parts = [];
      if (t.source) parts.push(t.source);
      if (t.phase) parts.push(t.phase);
      if (t.tool) parts.push('tool:' + t.tool);
      if (t.trace_id) parts.push('trace:' + String(t.trace_id).slice(0, 8) + '…');
      const p = t.payload || {};
      if (p.correlation && p.correlation.request_id) {
        parts.push('req:' + String(p.correlation.request_id).slice(0, 10) + (p.correlation.request_id.length > 10 ? '…' : ''));
      }
      const o = p.orchestration;
      if (o && o.intent) parts.push('intent:' + o.intent);
      if (o && o.execution_mode) parts.push('mode:' + o.execution_mode);
      if (p.metrics && p.metrics.total_ms != null) parts.push(String(p.metrics.total_ms) + 'ms');
      return parts.join(' · ');
    };

    return { isCollapsed, canCollapse, toggleCollapse, getStepIcon, formatStepMeta };
  },
};
</script>

<style scoped>
.thinking-card {
  margin-top: 20px;
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 14px;
  color: #aaa;
}

.thinking-header.clickable {
  cursor: pointer;
  user-select: none;
}

.thinking-header.clickable:hover {
  color: #e94560;
}

.collapse-icon {
  margin-left: auto;
  font-size: 10px;
  transition: transform 0.2s;
}

.thinking-icon {
  font-size: 18px;
}

.thinking-title {
  font-weight: 500;
}

.thinking-pulse {
  width: 8px;
  height: 8px;
  background: #e94560;
  border-radius: 50%;
  animation: pulse 1.2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.3); }
}

.thinking-steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.thinking-step {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
  font-size: 13px;
  color: #999;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  animation: fadeIn 0.3s ease-in;
}

.thinking-step.has-trace {
  border-left: 2px solid rgba(233, 69, 96, 0.45);
}

.step-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.event-badge {
  margin-left: auto;
  font-size: 10px;
  font-family: ui-monospace, monospace;
  color: #e94560;
  background: rgba(233, 69, 96, 0.12);
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.step-meta {
  font-size: 11px;
  color: #666;
  padding-left: 28px;
  line-height: 1.4;
}

.step-details {
  font-size: 11px;
  color: #777;
  padding-left: 24px;
}

.step-details summary {
  cursor: pointer;
  color: #888;
}

.node-list {
  margin: 6px 0 0 0;
  padding-left: 18px;
  color: #888;
}

.thinking-step.tool_call {
  color: #67c23a;
  background: rgba(103, 194, 58, 0.05);
}

.thinking-step.error {
  color: #f56c6c;
  background: rgba(245, 108, 108, 0.05);
}

.thinking-step.agent_finish {
  color: #e94560;
  background: rgba(233, 69, 96, 0.05);
}

.step-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.step-message {
  flex: 1;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
