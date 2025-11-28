<template>
  <el-container class="app-container">
    <!-- 导航栏 -->
    <el-header class="app-header">
      <el-menu 
        :default-active="$route.path" 
        mode="horizontal" 
        router 
        class="app-menu"
        :ellipsis="false"
      >
        <el-menu-item index="/">图片识别</el-menu-item>
        <el-menu-item index="/video">视频追踪</el-menu-item>
        <el-menu-item index="/camera">摄像头</el-menu-item>
        <el-menu-item index="/records">历史记录</el-menu-item>
      </el-menu>
    </el-header>

    <!-- 主内容区域 -->
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
// 这里可以放置任何需要初始化的逻辑
</script>

<style scoped>
.app-header {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 0;
  height: 60px; /* 确保 header 高度合适 */
}

.app-menu {
  background-color: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  width: fit-content;
  flex: none;
}

/* 设置背景图片 */
.app-container {
  position: relative;
  min-height: 100vh; 
  display: flex;
  flex-direction: column;
  background-image: url('@/views/preview.gif');
  background-size: cover;
  background-repeat: no-repeat;
  background-position: center;
}

.app-container::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: inherit;
  background-size: cover;
  background-repeat: no-repeat;
  background-position: center;
  z-index: -1;
  opacity: 0.6; /* 调整动图透明度，避免过强 */
}

/* 新增：深色半透明蒙层 */
.app-container::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.2); /* 深色蒙层，提升对比度 */
  z-index: -1;
  pointer-events: none;
}

/* 主内容区域 */
/* AppLayout.vue 中的 .app-main */
.app-main {
  flex: 1;
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.95);
  box-shadow: 0 0 15px rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  margin: 20px auto;
  max-width: 900px;
}

/* 导航栏 */
.app-menu {
  background-color: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

.app-menu .el-menu-item {
  color: #333;
  font-weight: 500;
}

.app-menu .el-menu-item:hover,
.app-menu .el-menu-item.is-active {
  background-color: rgba(255, 105, 180, 0.4);
  color: white;
}
</style>