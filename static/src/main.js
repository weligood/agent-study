/**
 * 应用入口：使用 vue3-sfc-loader 在浏览器中直接加载 .vue 组件
 * 无需 Vite / Webpack 等构建工具
 */
const { createApp } = Vue;
const { loadModule } = window['vue3-sfc-loader'];

// sfc-loader 配置
const sfcLoaderOptions = {
  // 模块缓存：注入全局的 Vue / ElementPlus
  moduleCache: {
    vue: Vue,
  },

  // 文件获取器：通过 fetch 拿到 .vue 源码
  async getFile(url) {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`无法加载模块: ${url}  (${res.status} ${res.statusText})`);
    }
    return res.text();
  },

  // 样式注入器：把 <style> 内容写进 <head>
  addStyle(textContent) {
    const style = Object.assign(document.createElement('style'), { textContent });
    document.head.appendChild(style);
  },
};

/**
 * 加载 .vue 组件的辅助函数
 * @param {string} path - 相对于 /src 的路径，如 './App.vue'
 */
function load(path) {
  return loadModule(path, sfcLoaderOptions);
}

// 启动 Vue 应用
(async () => {
  const App = await load('/src/App.vue');
  const app = createApp(App);
  app.use(ElementPlus);
  app.mount('#app');
})();
