<template>
  <div class="camera-page">
    <h2 class="page-title">摄像头识别</h2>

    <!-- 视频区域 -->
    <div class="video-container">
      <video
        ref="localVideo"
        autoplay
        playsinline
        class="camera-video"
      ></video>
    </div>

    <!-- 按钮区域：居中并排 -->
    <div class="button-group">
      <el-button type="primary" @click="startCamera" :disabled="streaming">打开摄像头</el-button>
      <el-button @click="stopCamera" :disabled="!streaming">关闭摄像头</el-button>
      <el-button type="success" @click="captureFrame" :disabled="!streaming">抓拍并识别</el-button>
    </div>

    <!-- 识别结果 -->
    <div v-if="lastResult" class="result-section">
      <h3>最后一次抓拍识别</h3>
      <img :src="lastResultUrl" class="result-image" />
      <pre class="result-json">{{ JSON.stringify(lastResult.objects, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { postCameraFrame } from '../api'

const localVideo = ref(null)
const streamRef = ref(null)
const streaming = ref(false)
const lastResult = ref(null)
const lastResultUrl = ref("")

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    streamRef.value = stream
    localVideo.value.srcObject = stream
    streaming.value = true
  } catch (e) {
    alert("无法打开摄像头: " + e.message)
  }
}

function stopCamera() {
  if (streamRef.value) {
    streamRef.value.getTracks().forEach(t => t.stop())
    streamRef.value = null
    streaming.value = false
  }
}

function captureFrame() {
  const video = localVideo.value
  const canvas = document.createElement("canvas")
  canvas.width = video.videoWidth || 640
  canvas.height = video.videoHeight || 480
  const ctx = canvas.getContext("2d")
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
  canvas.toBlob(async (blob) => {
    const res = await postCameraFrame(blob, "frame.jpg")
    lastResult.value = res
    lastResultUrl.value = `http://localhost:8000${res.result_url}`
  }, "image/jpeg", 0.9)
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

/* 视频容器：确保视频居中且响应式 */
.video-container {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.camera-video {
  width: 100%;
  max-width: 600px; /* 不超过 600px */
  height: auto;
  border: 1px solid #ccc;
  border-radius: 8px;
  display: block;
}

/* 按钮组：水平居中 */
.button-group {
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap; /* 小屏自动换行 */
  margin-bottom: 24px;
}

.button-group .el-button {
  min-width: 100px;
}

/* 结果区域 */
.result-section {
  text-align: center;
}

.result-image {
  max-width: 90%;
  height: auto;
  border-radius: 6px;
  margin: 12px 0;
  display: block;
}

.result-json {
  max-width: 90%;
  margin: 16px auto 0;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  text-align: left;
  font-size: 14px;
  overflow-x: auto;
}
</style>