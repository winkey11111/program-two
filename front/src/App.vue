<template>
  <el-container style="height:100vh">
    <el-header>
      <el-menu :default-active="$route.path" mode="horizontal" router>
        <el-menu-item index="/">Image</el-menu-item>
        <el-menu-item index="/video">Video</el-menu-item>
        <el-menu-item index="/camera">Camera</el-menu-item>
        <el-menu-item index="/records">Records</el-menu-item>
      </el-menu>
    </el-header>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
</script>
