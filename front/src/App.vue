<template>
  <el-container class="app-container">
    <!-- 导航栏 -->
    <el-header class="app-header">
      <el-menu 
        :default-active="$route.path" 
        mode="horizontal" 
        router 
        class="app-menu"
      >
        <el-menu-item index="/">Image</el-menu-item>
        <el-menu-item index="/video">Video</el-menu-item>
        <el-menu-item index="/camera">Camera</el-menu-item>
        <el-menu-item index="/records">Records</el-menu-item>
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
/* 设置背景图片 */
.app-container::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: url('.\views\preview.gif');
  background-size: cover;
  background-position: center;
  z-index: -1; /* 确保背景在所有元素之下 */
  opacity: 0.6; /* 调整动图透明度，避免过强 */
}

/* 新增：深色半透明蒙层 —— 关键优化！ */
.app-container::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.2); /* 深色蒙层，提升对比度 */
  z-index: -1; /* 在动图之上，容器之下 */
  pointer-events: none; /* 不影响点击 */
}

/* 主内容区域 —— 提高不透明度，增强可读性 */
.app-main {
  flex: 1;
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.95); /* ↑ 提高到 0.95 */
  box-shadow: 0 0 15px rgba(0, 0, 0, 0.2); /* 更明显阴影 */
  border-radius: 12px;
  margin: 20px auto; /* 居中显示 */
  max-width: 800px; /* 限制宽度，更聚焦 */
}

/* 导航栏 —— 加深背景，确保清晰可见 */
.app-menu {
  background-color: rgba(255, 255, 255, 0.9); /* 更白更清晰 */
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

.app-menu .el-menu-item {
  color: #333;
  font-weight: 500;
}

.app-menu .el-menu-item:hover,
.app-menu .el-menu-item.is-active {
  background-color: rgba(255, 105, 180, 0.4); /* 淡粉红，呼应红调 */
  color: white;
}
</style>