<template>
  <header class="app-header">
    <div class="logo">
      <span class="logo-icon">🎬</span>
      <div class="logo-text">
        <h1>正版追剧助手</h1>
        <p>TV Legal Availability</p>
      </div>
    </div>
    <p class="subtitle">查询电视剧正版播放平台 · 合规渠道聚合</p>
  </header>
</template>

<script>
export default {
  name: 'AppHeader'
};
</script>

<style scoped>
.app-header {
  text-align: center;
  margin-bottom: 40px;
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 8px;
}

.logo-icon {
  font-size: 40px;
}

.logo-text h1 {
  font-size: 32px;
  font-weight: 700;
  background: linear-gradient(90deg, #e94560, #ff6b6b);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}

.logo-text p {
  margin: 4px 0 0;
  color: #e94560;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.subtitle {
  color: #a0a0a0;
  font-size: 14px;
  margin: 0;
}
</style>
