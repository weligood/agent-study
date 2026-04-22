<template>
  <div class="search-card">
    <!-- 查询类型切换 -->
    <div class="search-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.type"
        class="tab-btn"
        :class="{ active: queryType === tab.type }"
        @click="queryType = tab.type"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- 搜索输入 -->
    <div class="search-input-group">
      <el-input
        v-model="query"
        class="search-input"
        :placeholder="currentPlaceholder"
        size="large"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <span class="input-icon">{{ currentIcon }}</span>
        </template>
      </el-input>
      <button class="search-btn" @click="handleSearch" :disabled="loading">
        <span v-if="loading" class="loading-spinner"></span>
        <span v-else>查询</span>
      </button>
    </div>

    <!-- 消歧提示 -->
    <el-input
      v-if="queryType !== 'video'"
      v-model="hint"
      class="hint-input"
      placeholder="消歧提示：年份如 2023，或 work_id（可选）"
      size="default"
    />

    <div v-if="queryType !== 'video'" class="pref-row">
      <label class="pref-label"><input type="checkbox" v-model="prefOfficialOnly" /> 仅官方入口</label>
      <label class="pref-label"><input type="checkbox" v-model="prefHideRent" /> 隐藏「租赁」类 offer</label>
    </div>
  </div>
</template>

<script>
const { ref, computed } = Vue;

export default {
  name: 'SearchCard',
  props: {
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['search'],
  setup(props, { emit }) {
    const queryType = ref('title');
    const query = ref('');
    const hint = ref('');
    const prefOfficialOnly = ref(false);
    const prefHideRent = ref(false);

    const tabs = [
      { type: 'title', label: '按剧名查询', icon: '📺' },
      { type: 'actor', label: '按演员查询', icon: '🎭' },
      { type: 'video', label: '视频解析', icon: '🔗' }
    ];

    const currentPlaceholder = computed(() => {
      if (queryType.value === 'title') return '输入电视剧名称，例如：狂飙';
      if (queryType.value === 'actor') return '输入演员姓名，例如：张译';
      return '粘贴官方视频页面链接，例如：https://www.bilibili.com/video/...';
    });

    const currentIcon = computed(() => {
      if (queryType.value === 'title') return '📺';
      if (queryType.value === 'actor') return '🎭';
      return '🔗';
    });

    const buildPreferences = () => {
      const o = {};
      if (prefOfficialOnly.value) o.official_only = true;
      if (prefHideRent.value) o.excluded_access_types = ['rent'];
      return Object.keys(o).length ? o : null;
    };

    const handleSearch = () => {
      if (!query.value.trim()) return;
      emit('search', {
        queryType: queryType.value,
        query: query.value.trim(),
        hint: queryType.value === 'video' ? '' : hint.value.trim(),
        preferences: queryType.value === 'video' ? null : buildPreferences(),
      });
    };

    return {
      queryType,
      query,
      hint,
      prefOfficialOnly,
      prefHideRent,
      tabs,
      currentPlaceholder,
      currentIcon,
      handleSearch
    };
  }
};
</script>

<style scoped>
.search-card {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 30px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.search-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 24px;
}

.tab-btn {
  flex: 1;
  min-width: 150px;
  padding: 12px 24px;
  border: none;
  background: rgba(255, 255, 255, 0.05);
  color: #a0a0a0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.tab-btn.active {
  background: linear-gradient(90deg, #e94560, #ff6b6b);
  color: #fff;
}

.tab-btn:hover:not(.active) {
  background: rgba(255, 255, 255, 0.1);
}

.tab-icon {
  font-size: 16px;
}

.search-input-group {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input {
  flex: 1;
}

.search-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.08);
  box-shadow: none;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.search-input :deep(.el-input__inner) {
  color: #fff;
  height: 48px;
  font-size: 15px;
}

.search-input :deep(.el-input__inner::placeholder) {
  color: #666;
}

.input-icon {
  font-size: 18px;
  margin-right: 4px;
}

.search-btn {
  height: 48px;
  padding: 0 32px;
  background: linear-gradient(90deg, #e94560, #ff6b6b);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(233, 69, 96, 0.3);
}

.search-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.hint-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  box-shadow: none;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.hint-input :deep(.el-input__inner) {
  color: #ccc;
  height: 40px;
  font-size: 13px;
}

.pref-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 12px;
  font-size: 13px;
  color: #999;
}

.pref-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
}

.pref-label input {
  accent-color: #e94560;
}

.loading-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
