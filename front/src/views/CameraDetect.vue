<template>
  <div class="camera-page">
    <h2 class="page-title">摄像头实时识别</h2>

    <div class="video-container">
      <img
        v-if="streaming"
        :src="streamUrl"
        class="camera-video"
      />
      <div v-else class="placeholder">
        点击“打开摄像头”开始实时识别
      </div>
    </div>

    <div class="button-group">
      <el-button type="primary" @click="startStream" :disabled="streaming">
        打开摄像头
      </el-button>
      <el-button @click="stopStream" :disabled="!streaming">
        关闭摄像头
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const streaming = ref(false)
const streamUrl = ref("")

function startStream() {
  streaming.value = true
  streamUrl.value = "http://localhost:8000/api/camera/stream?t=" + Date.now()
}

function stopStream() {
  streaming.value = false
  streamUrl.value = ""
}
</script>

<style scoped>
.camera-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 0 16px 16px;
  width: 100%;
  box-sizing: border-box;
}

.page-title {
  text-align: center;
  margin-bottom: 24px;
  color: #333;
}

.video-container {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
  width: 100%;
}

.camera-video {
  width: 100%;
  max-width: 700px;
  height: auto;
  border: 1px solid #ccc;
  border-radius: 8px;
}

.placeholder {
  width: 100%;
  max-width: 700px;
  height: 400px;
  border: 2px dashed #cccccc;
  border-radius: 8px;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #777;
  font-size: 18px;
}

.button-group {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 24px;
}

.button-group .el-button {
  min-width: 120px;
}
</style>
