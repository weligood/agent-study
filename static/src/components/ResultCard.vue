<template>
  <div class="result-card">
    <div class="result-header">
      <h3>查询结果</h3>
      <el-tag :type="statusType">{{ statusText }}</el-tag>
    </div>

    <!-- 元信息 -->
    <div v-if="showMeta" class="meta-grid">
      <div class="meta-item">
        <div class="meta-label">查询内容</div>
        <div class="meta-value">{{ result.query_title }}</div>
      </div>
      <div v-if="result.standard_title" class="meta-item">
        <div class="meta-label">标准名称</div>
        <div class="meta-value">{{ result.standard_title }}</div>
      </div>
      <div v-if="result.release_year" class="meta-item">
        <div class="meta-label">上映年份</div>
        <div class="meta-value">{{ result.release_year }}</div>
      </div>
      <div v-if="result.region" class="meta-item">
        <div class="meta-label">地区</div>
        <div class="meta-value">{{ result.region }}</div>
      </div>
      <div v-if="result.episodes" class="meta-item">
        <div class="meta-label">集数</div>
        <div class="meta-value">{{ result.episodes }}集</div>
      </div>
    </div>

    <div v-if="result.response_meta" class="response-meta-bar">
      <span v-if="result.response_meta.request_id" class="rm">请求 ID: <code>{{ result.response_meta.request_id }}</code></span>
      <span v-if="result.response_meta.trace_id" class="rm">Trace: <code>{{ shortId(result.response_meta.trace_id) }}</code></span>
      <span v-if="result.response_meta.intent" class="rm">{{ result.response_meta.intent }}</span>
      <span v-if="result.response_meta.execution_mode" class="rm">{{ result.response_meta.execution_mode }}</span>
      <span v-if="result.response_meta.total_ms != null" class="rm">{{ result.response_meta.total_ms }} ms</span>
    </div>

    <!-- 候选剧集 -->
    <template v-if="result.candidate_titles?.length">
      <div class="section-title">候选剧集（点击选择）</div>
      <div class="candidates-grid">
        <div
          v-for="item in result.candidate_titles"
          :key="item.work_id || item.standard_title"
          class="candidate-card"
          @click="$emit('select-candidate', item)"
        >
          <div class="candidate-title">{{ item.standard_title }}</div>
          <div class="candidate-meta">
            {{ formatCandidateMeta(item) }}
          </div>
        </div>
      </div>
    </template>

    <!-- 视频解析与下载 -->
    <template v-if="result.video_info">
      <div class="section-title">视频解析</div>
      <div class="video-panel">
        <img
          v-if="result.video_info.thumbnail"
          :src="result.video_info.thumbnail"
          :alt="result.video_info.title || '视频封面'"
          class="video-thumb"
          @error="(e) => e.target.style.display = 'none'"
        />
        <div class="video-body">
          <div class="video-title">{{ result.video_info.title || result.query_title }}</div>
          <div class="video-meta">
            <span v-if="result.video_info.platform">{{ result.video_info.platform }}</span>
            <span v-if="result.video_info.uploader">{{ result.video_info.uploader }}</span>
            <span v-if="result.video_info.duration_display || result.video_info.duration">
              {{ result.video_info.duration_display || formatDuration(result.video_info.duration) }}
            </span>
          </div>
          <div v-if="videoQualities.length" class="quality-list">
            <button
              v-for="q in videoQualities"
              :key="q.quality + '-' + (q.width || '') + '-' + (q.height || '')"
              class="quality-btn"
              :disabled="downloadBusy"
              @click="prepareDownload(q.quality)"
            >
              {{ qualityLabel(q) }}
            </button>
          </div>
          <div v-else class="video-note">未解析到可下载清晰度，可能需要登录、会员或平台未开放直链。</div>

          <div class="download-actions">
            <button
              class="download-btn"
              :disabled="downloadBusy || !result.video_info.url"
              @click="prepareDownload('highest')"
            >
              {{ downloadBusy ? '处理中…' : '准备下载最高画质' }}
            </button>
            <span class="download-hint">下载前会先创建任务，需要再次确认。</span>
          </div>

          <div v-if="pendingDownload" class="download-confirm">
            <div>
              已准备下载：{{ pendingDownload.title || pendingDownload.platform || '视频' }}
              <span v-if="pendingDownload.task_id"> · {{ shortId(pendingDownload.task_id) }}</span>
            </div>
            <button class="confirm-btn" :disabled="downloadBusy" @click="confirmDownload">
              确认下载
            </button>
          </div>

          <div v-if="downloadResult" class="download-result" :class="{ failed: !downloadResult.success }">
            {{ downloadResult.message || (downloadResult.success ? '下载完成' : '下载失败') }}
            <div v-if="downloadResult.file_path" class="download-path">{{ downloadResult.file_path }}</div>
          </div>
        </div>
      </div>
    </template>

    <!-- 平台列表 -->
    <template v-if="result.platforms?.length">
      <div class="section-title">正版播放平台</div>
      <div class="platform-grid">
        <a
          v-for="platform in result.platforms"
          :key="platform.platform_name"
          class="platform-card"
          :href="platformHref(platform)"
          target="_blank"
          rel="noopener noreferrer"
        >
          <div class="platform-header">
            <div class="platform-name-row">
              <img
                v-if="platform.logo_url || platformLogo(platform.platform_name)"
                :src="platform.logo_url || platformLogo(platform.platform_name)"
                :alt="platform.platform_name"
                class="platform-logo"
                @error="(e) => e.target.style.display = 'none'"
              />
              <span class="platform-name">{{ platform.platform_name }}</span>
            </div>
            <span
              class="platform-status"
              :class="platform.availability_status"
            >
              {{ platform.availability_status === 'available' ? '可观看' : '暂不可用' }}
            </span>
          </div>
          <div class="platform-tags">
            <span
              class="platform-tag"
              :class="{ vip: platform.membership_required, free: platform.membership_required === false }"
            >
              {{ getMembershipText(platform.membership_required) }}
            </span>
            <span v-if="platform.offline_download_supported" class="platform-tag">
              ⬇️ 可下载
            </span>
            <span class="platform-tag">
              {{ getPaymentText(platform.payment_type) }}
            </span>
          </div>
          <div class="platform-action">
            打开官方搜索 →
          </div>
        </a>
      </div>
    </template>

    <!-- 相似剧推荐 -->
    <template v-if="result.similar_titles?.length">
      <div class="section-title">相似剧推荐</div>
      <div class="candidates-grid">
        <div
          v-for="item in result.similar_titles"
          :key="item.work_id || item.standard_title"
          class="candidate-card similar-card"
          @click="$emit('select-candidate', item)"
        >
          <div class="candidate-title">{{ item.standard_title }}</div>
          <div class="candidate-meta">
            {{ formatCandidateMeta(item) }}
          </div>
        </div>
      </div>
    </template>

    <!-- 追问输入 -->
    <div class="follow-up-section" v-if="result.result_status === 'success'">
      <div class="section-title">继续追问</div>
      <div class="follow-up-input-group">
        <el-input
          v-model="followUpText"
          class="follow-up-input"
          placeholder="这部剧的导演还有什么作品？ / 有没有类似的剧？"
          size="default"
          @keyup.enter="submitFollowUp"
        />
        <button class="follow-up-btn" @click="submitFollowUp">发送</button>
      </div>
    </div>

    <!-- 免责声明 -->
    <el-alert
      v-if="result.disclaimer"
      :title="result.disclaimer"
      type="info"
      :closable="false"
      class="disclaimer-alert"
    />
  </div>
</template>

<script>
const { computed, ref, watch } = Vue;

// 平台名称 → 备用 logo（favicon）映射（后端会返回 logo_url，此处仅作 fallback）
const FALLBACK_LOGOS = {
  '爱奇艺': 'https://www.iqiyi.com/favicon.ico',
  '腾讯视频': 'https://v.qq.com/favicon.ico',
  '优酷': 'https://www.youku.com/favicon.ico',
  '芒果TV': 'https://www.mgtv.com/favicon.ico',
  '哔哩哔哩': 'https://www.bilibili.com/favicon.ico',
  'Netflix': 'https://www.netflix.com/favicon.ico',
  '央视网': 'https://tv.cctv.com/favicon.ico',
};
const platformLogo = (name) => FALLBACK_LOGOS[name] || null;
const shortId = (s) => (s && s.length > 12 ? s.slice(0, 8) + '…' : (s || ''));

const getStatusText = (s) => ({ success:'查询成功', ambiguous:'需要消歧', not_found:'未找到', partial:'部分信息' })[s] || s;
const getStatusType = (s) => ({ success:'success', ambiguous:'warning', not_found:'danger', partial:'info' })[s] || 'info';
const getPaymentText = (t) => ({ free:'免费', subscription:'会员订阅', rental:'租赁', purchase:'购买', ad_supported:'广告支持', unknown:'未知' })[t] || t;
const officialSearchUrl = (platformName, title) => {
  const q = encodeURIComponent(title || '');
  if (!q) return null;
  const map = {
    '爱奇艺': `https://so.iqiyi.com/so/q_${q}`,
    '腾讯视频': `https://v.qq.com/x/search/?q=${q}`,
    '优酷': `https://search.youku.com/search_video?keyword=${q}`,
    '哔哩哔哩': `https://search.bilibili.com/all?keyword=${q}`,
    '芒果TV': `https://www.mgtv.com/so/${q}.html`,
    'Netflix': `https://www.netflix.com/search?q=${q}`,
    '央视网': `https://tv.cctv.com/search/?qtext=${q}`,
  };
  return map[platformName] || null;
};
const formatDuration = (seconds) => {
  const n = Number(seconds || 0);
  if (!n) return '';
  const m = Math.floor(n / 60);
  const s = n % 60;
  return `${m}分${String(s).padStart(2, '0')}秒`;
};

export default {
  name: 'ResultCard',
  props: {
    result: {
      type: Object,
      required: true
    }
  },
  emits: ['select-candidate', 'follow-up'],
  setup(props, { emit }) {
    const statusText = computed(() => getStatusText(props.result.result_status));
    const statusType = computed(() => getStatusType(props.result.result_status));
    const pendingDownload = ref(null);
    const downloadResult = ref(null);
    const downloadBusy = ref(false);

    const showMeta = computed(() => {
      return props.result.standard_title ||
             props.result.release_year ||
             props.result.region;
    });
    const videoQualities = computed(() => props.result.video_info?.available_qualities || []);

    watch(
      () => props.result,
      () => {
        pendingDownload.value = null;
        downloadResult.value = null;
        downloadBusy.value = false;
      },
    );

    const formatCandidateMeta = (item) => {
      return [item.release_year, item.region, item.brief_note]
        .filter(Boolean)
        .join(' · ');
    };

    const getMembershipText = (required) => {
      if (required === null) return '会员未知';
      return required ? '需要会员' : '免会员';
    };
    const platformHref = (platform) => {
      const title = props.result.standard_title || props.result.query_title;
      return officialSearchUrl(platform.platform_name, title) ||
        (platform.official_url && platform.official_url.startsWith('http') ? platform.official_url : '#');
    };
    const qualityLabel = (q) => {
      const size = q.width && q.height ? ` · ${q.width}x${q.height}` : '';
      return `${q.quality || '默认'}${size}`;
    };
    const postJson = async (url, payload) => {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || '请求失败');
      return data;
    };
    const prepareDownload = async (quality) => {
      if (!props.result.video_info?.url) return;
      downloadBusy.value = true;
      downloadResult.value = null;
      try {
        const data = await postJson('/api/video/download/prepare', {
          video_url: props.result.video_info.url,
          quality,
        });
        if (data.policy_blocked) {
          ElementPlus.ElMessage.warning(data.message || '当前未开放下载');
          return;
        }
        if (!data.ok) {
          ElementPlus.ElMessage.error(data.message || '准备下载失败');
          return;
        }
        if (data.download_eligible === false) {
          ElementPlus.ElMessage.warning('没有可下载格式，可能需要登录、会员或平台未开放直链');
          return;
        }
        pendingDownload.value = data;
        ElementPlus.ElMessage.success('下载任务已准备，请确认后开始');
      } catch (e) {
        ElementPlus.ElMessage.error(e.message || '准备下载失败');
      } finally {
        downloadBusy.value = false;
      }
    };
    const confirmDownload = async () => {
      if (!pendingDownload.value?.task_id) return;
      downloadBusy.value = true;
      try {
        const data = await postJson('/api/video/download/confirm', {
          task_id: pendingDownload.value.task_id,
        });
        downloadResult.value = data;
        if (data.success) {
          ElementPlus.ElMessage.success(data.message || '下载完成');
          pendingDownload.value = null;
        } else {
          ElementPlus.ElMessage.error(data.message || '下载失败');
        }
      } catch (e) {
        ElementPlus.ElMessage.error(e.message || '下载失败');
      } finally {
        downloadBusy.value = false;
      }
    };

    const followUpText = ref('');
    const submitFollowUp = () => {
      const text = followUpText.value.trim();
      if (text) {
        emit('follow-up', text);
        followUpText.value = '';
      }
    };

    return {
      statusText,
      statusType,
      showMeta,
      videoQualities,
      formatCandidateMeta,
      formatDuration,
      getMembershipText,
      getPaymentText,
      platformHref,
      platformLogo,
      shortId,
      qualityLabel,
      prepareDownload,
      confirmDownload,
      pendingDownload,
      downloadResult,
      downloadBusy,
      followUpText,
      submitFollowUp,
    };
  }
};
</script>

<style scoped>
.result-card {
  margin-top: 30px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.result-header h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.meta-item {
  background: rgba(255, 255, 255, 0.05);
  padding: 16px;
  border-radius: 12px;
}

.meta-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}

.meta-value {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}

.response-meta-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  font-size: 11px;
  color: #888;
  margin: -8px 0 20px 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.response-meta-bar .rm code {
  font-family: ui-monospace, monospace;
  font-size: 10px;
  color: #b0b0b0;
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 6px;
  border-radius: 4px;
}

.section-title {
  font-size: 14px;
  color: #888;
  margin: 24px 0 16px;
  font-weight: 500;
}

.candidates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.candidate-card {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.candidate-card:hover {
  border-color: #e94560;
  background: rgba(233, 69, 96, 0.1);
}

.candidate-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.candidate-meta {
  font-size: 12px;
  color: #888;
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.video-panel {
  display: flex;
  gap: 18px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 18px;
  margin-bottom: 24px;
}

.video-thumb {
  width: 180px;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.25);
  flex: 0 0 auto;
}

.video-body {
  flex: 1;
  min-width: 0;
}

.video-title {
  font-size: 17px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 8px;
  overflow-wrap: anywhere;
}

.video-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  color: #999;
  font-size: 13px;
  margin-bottom: 14px;
}

.quality-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.quality-btn,
.download-btn,
.confirm-btn {
  border: none;
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s;
}

.quality-btn {
  padding: 7px 12px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 12px;
}

.quality-btn:hover:not(:disabled) {
  background: rgba(233, 69, 96, 0.35);
}

.download-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.download-btn,
.confirm-btn {
  padding: 9px 16px;
  background: linear-gradient(135deg, #e94560, #c23152);
  font-size: 13px;
  font-weight: 600;
}

.quality-btn:disabled,
.download-btn:disabled,
.confirm-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.download-hint,
.video-note {
  color: #999;
  font-size: 12px;
}

.download-confirm,
.download-result {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
  background: rgba(103, 194, 58, 0.12);
  border: 1px solid rgba(103, 194, 58, 0.25);
  color: #d7f5ce;
}

.download-confirm {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.download-result.failed {
  background: rgba(245, 108, 108, 0.12);
  border-color: rgba(245, 108, 108, 0.25);
  color: #f5c6c6;
}

.download-path {
  margin-top: 6px;
  color: #aaa;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
}

@media (max-width: 640px) {
  .video-panel {
    flex-direction: column;
  }

  .video-thumb {
    width: 100%;
  }

  .download-confirm {
    align-items: stretch;
    flex-direction: column;
  }
}

.platform-card {
  display: block;
  text-decoration: none;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.platform-card:hover {
  transform: translateY(-4px);
  border-color: #e94560;
  box-shadow: 0 12px 30px rgba(233, 69, 96, 0.2);
}

.platform-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.platform-name-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.platform-logo {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  object-fit: contain;
  background: rgba(255,255,255,0.1);
  padding: 2px;
}

.platform-name {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
}

.platform-status {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 20px;
  font-weight: 500;
}

.platform-status.available {
  background: rgba(103, 194, 58, 0.2);
  color: #67c23a;
}

.platform-status.unavailable {
  background: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
}

.platform-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.platform-tag {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  color: #ccc;
}

.platform-tag.vip {
  background: rgba(233, 69, 96, 0.2);
  color: #e94560;
}

.platform-tag.free {
  background: rgba(103, 194, 58, 0.2);
  color: #67c23a;
}

.platform-action {
  text-align: center;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  color: #e94560;
  font-size: 14px;
  font-weight: 500;
}

.similar-card {
  border-color: rgba(64, 158, 255, 0.3);
}

.similar-card:hover {
  border-color: #409eff;
  background: rgba(64, 158, 255, 0.1);
}

.follow-up-section {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.follow-up-input-group {
  display: flex;
  gap: 10px;
  align-items: center;
}

.follow-up-input {
  flex: 1;
}

.follow-up-btn {
  padding: 8px 20px;
  background: linear-gradient(135deg, #e94560, #c23152);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
  white-space: nowrap;
}

.follow-up-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(233, 69, 96, 0.4);
}

.disclaimer-alert {
  margin-top: 20px;
}

.disclaimer-alert :deep(.el-alert__title) {
  font-size: 13px;
  line-height: 1.6;
}
</style>
