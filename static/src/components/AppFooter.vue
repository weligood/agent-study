<template>
  <footer class="app-footer">
    <p>仅展示正版平台信息，不提供任何盗版或绕过版权的内容</p>
    <p class="footer-note">数据仅供参考，请以各平台官方页面为准</p>
  </footer>
</template>

<script>
export default {
  name: 'AppFooter'
};
</script>

<style scoped>
.app-footer {
  text-align: center;
  padding: 30px 20px;
  color: #666;
  font-size: 13px;
}

.app-footer p {
  margin: 4px 0;
}

.footer-note {
  opacity: 0.8;
}
</style>
