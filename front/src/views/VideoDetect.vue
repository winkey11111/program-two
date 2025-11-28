<template>
  <div class="video-detect-container">
    <!-- 标题 -->
    <div style="display: flex; justify-content: center; margin-bottom: 16px;">
      <h2 style="margin: 0;">视频识别</h2>
    </div>

    <!-- 控制按钮 -->
    <div class="upload-actions">
      <el-upload :before-upload="beforeUpload" :show-file-list="false">
        <el-button>选择视频</el-button>
      </el-upload>
      <el-button type="primary" :disabled="!file" @click="upload">上传处理</el-button>
      <el-button @click="clearResult" class="ml-8">清空</el-button>
    </div>

    <!-- 主内容区：始终显示双栏 -->
    <div class="outer-frame">
      <div v-if="result && result.status !== 'completed'" class="processing-banner">
        视频正在后台处理中，请稍后刷新或查看<a href="/#/records">历史记录</a>。
      </div>

      <div class="result-layout">
        <!-- 视频预览区 -->
        <div class="preview-section">
          <h3>视频预览</h3>
          <div class="inner-frame" style="position: relative; overflow: hidden;">
            <video
              v-if="result?.status === 'completed'"
              ref="videoRef"
              :src="resultUrl"
              controls
              class="preview-video"
              @timeupdate="onTimeUpdate"
            ></video>
            <canvas
              v-if="result?.status === 'completed'"
              ref="overlayCanvasRef"
              class="overlay-canvas"
            ></canvas>

            <!-- 占位提示 -->
            <div v-if="!result || result.status !== 'completed'" class="empty-placeholder">
              <el-icon class="empty-icon"><VideoCamera /></el-icon>
              <p>{{ file ? '视频处理中…' : '请上传视频' }}</p>
            </div>
          </div>
        </div>

        <!-- 检测结果表格 -->
        <div class="detection-section">
          <h3>识别结果{{ currentFrameIndex >= 0 ? `（第 ${currentFrameIndex} 帧）` : '' }}</h3>
          <div class="inner-frame">
            <div v-if="result?.status === 'completed' && currentFrameObjects?.length">
              <el-table
                :data="currentFrameObjects"
                style="width: 100%"
                table-layout="fixed"
                height="340"
              >
                <el-table-column prop="class" label="类别" width="100" />
                <el-table-column label="置信度" width="100">
                  <template #default="{ row }">
                    {{ (row.conf * 100).toFixed(1) }}%
                  </template>
                </el-table-column>
                <el-table-column label="边界框" width="260" show-overflow-tooltip>
                  <template #default="{ row }">
                    {{ row.bbox?.map(v => Math.round(v)).join(', ') }}
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <el-empty
              v-else
              description="未检测到目标"
              style="margin-top: 80px;"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { uploadVideo } from '../api'
import { VideoCamera } from '@element-plus/icons-vue'

const file = ref(null)
const result = ref(null)
const resultUrl = ref('')
const videoRef = ref(null)
const overlayCanvasRef = ref(null)
const currentFrameObjects = ref(null)
const currentFrameIndex = ref(-1)

function beforeUpload(fileRaw) {
  file.value = fileRaw
  result.value = null
  currentFrameObjects.value = null
  currentFrameIndex.value = -1
  return false
}

async function upload() {
  if (!file.value) return
  try {
    const res = await uploadVideo(file.value)
    result.value = res
    resultUrl.value = `http://localhost:8000${res.result_url}`
  } catch (error) {
    console.error('上传失败:', error)
  }
}

function clearResult() {
  file.value = null
  result.value = null
  currentFrameObjects.value = null
  currentFrameIndex.value = -1
}

function onTimeUpdate() {
  // TODO: 后续根据视频时间戳匹配帧数据
  // 示例：假设后端返回 frames: [{ index, time, objects }, ...]
  // const currentTime = videoRef.value?.currentTime || 0
  // const frame = findClosestFrame(result.value.frames, currentTime)
  // currentFrameIndex.value = frame?.index || -1
  // currentFrameObjects.value = frame?.objects || []
}
</script>

<style scoped>
.video-detect-container {
  padding: 20px;
}

.upload-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.ml-8 {
  margin-left: 8px;
}

.processing-banner {
  background-color: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 4px;
  padding: 8px 12px;
  margin-bottom: 16px;
  color: #faad14;
  font-size: 14px;
}

.processing-banner a {
  color: #409eff;
  text-decoration: none;
}

/* 复用图片识别的样式结构 */
.outer-frame {
  width: 100%;
  min-height: 450px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 16px;
  box-sizing: border-box;
  background-color: #fafafa;
}

.result-layout {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  width: 100%;
  box-sizing: border-box;
}

.preview-section,
.detection-section {
  flex: 1;
  min-width: 300px;
  max-width: 50%;
}

h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #303133;
}

.inner-frame {
  width: 100%;
  height: 380px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  box-sizing: border-box;
  background-color: #fff;
  position: relative;
  overflow: hidden;
}

.preview-video,
.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.empty-placeholder {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #909399;
}

.empty-icon {
  font-size: 36px;
  margin-bottom: 12px;
}

.detection-section .inner-frame {
  overflow-y: auto;
  padding: 10px;
}

:deep(.el-empty) {
  margin: 60px 0;
}
</style>