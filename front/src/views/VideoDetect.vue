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

    <!-- 处理中进度提示 -->
    <div v-if="result && result.status === 'processing'" class="processing-banner">
      视频处理中：{{ progress }}%
      <el-progress :percentage="progress" :stroke-width="4" style="margin-top: 8px;" />
    </div>

    <!-- 主内容区：始终显示双栏 -->
    <div class="outer-frame">
      <div class="result-layout">
        <!-- 视频预览区 -->
        <div class="preview-section">
          <h3>视频预览</h3>
          <div class="inner-frame" style="position: relative; overflow: hidden;">
            <video
              v-if="previewVideoUrl || (result?.status === 'completed')"
              ref="videoRef"
              :src="result?.status === 'completed' ? resultUrlWithTimestamp : previewVideoUrl"
              controls
              class="preview-video"
              @timeupdate="onTimeUpdate"
            ></video>

            <!-- 占位提示 -->
            <div
              v-if="!previewVideoUrl && (!result || result.status !== 'completed')"
              class="empty-placeholder"
            >
              <el-icon class="empty-icon"><VideoCamera /></el-icon>
              <p>{{ file ? '视频处理中…' : '请上传视频' }}</p>
            </div>
          </div>
        </div>

        <!-- 检测结果表格 -->
        <div class="detection-section">
          <h3>识别结果{{ currentFrameIndex >= 0 ? `（第 ${currentFrameIndex} 帧）` : '' }}</h3>
          <div class="inner-frame">
            <div v-if="result?.status === 'completed' && allObjects?.length">
              <el-table
                :data="currentFrameObjects"
                style="width: 100%"
                table-layout="fixed"
                height="300"
              >
                <el-table-column prop="class" label="类别" width="100" />
                <el-table-column label="ID" width="70">
                  <template #default="{ row }">
                    {{ row.id }}
                  </template>
                </el-table-column>
                <el-table-column label="置信度" width="90">
                  <template #default="{ row }">
                    {{ (row.confidence * 100).toFixed(1) }}%
                  </template>
                </el-table-column>
                <el-table-column label="边界框" width="180" show-overflow-tooltip>
                  <template #default="{ row }">
                    {{ row.bbox?.map(v => Math.round(v)).join(', ') }}
                  </template>
                </el-table-column>
              </el-table>

              <!-- 所有物体列表 -->
              <div class="all-objects-section">
                <h4>所有检测物体</h4>
                <el-table
                  :data="allObjects"
                  style="width: 100%"
                  table-layout="fixed"
                  height="200"
                >
                  <el-table-column label="ID" width="70">
                    <template #default="{ row }">
                      {{ row.id }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="class" label="类别" width="100" />
                  <el-table-column label="出现次数" width="90">
                    <template #default="{ row }">
                      {{ row.appearances }}
                    </template>
                  </el-table-column>
                  <el-table-column label="首次出现" width="110">
                    <template #default="{ row }">
                      {{ formatTimestamp(row.first_seen) }}
                    </template>
                  </el-table-column>
                </el-table>
              </div>
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
import { ElMessage } from 'element-plus'
import { ref, onMounted, onUnmounted, computed } from 'vue'
import {
  uploadVideo,
  getVideoDetections,
  getVideoObjects,
  getVideoStatus
} from '../api'
import { VideoCamera } from '@element-plus/icons-vue'
import { useDetectStore } from '../stores/detect'

const store = useDetectStore()

// ========== 响应式状态 ==========
const file = ref(null)
const previewVideoUrl = ref('')
const result = ref(null)
const rawResultUrl = ref('')
const videoRef = ref(null)
const currentFrameObjects = ref([])
const currentFrameIndex = ref(-1)
const allObjects = ref([])
const videoId = ref('')
const pollingInterval = ref(null)
const isPolling = ref(false)
const progress = ref(0)

const videoInfo = ref({ fps: 25, total_frames: 0 })

const resultUrlWithTimestamp = computed(() => {
  return rawResultUrl.value ? `${rawResultUrl.value}?t=${Date.now()}` : ''
})

// ========== 工具函数 ==========
function formatTimestamp(seconds) {
  if (seconds == null) return '--'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

async function isVideoAccessible(url) {
  try {
    const response = await fetch(url, { method: 'HEAD' })
    return response.ok
  } catch (error) {
    console.warn('Video file not accessible yet:', url, error)
    return false
  }
}

// ========== 事件监听 ==========
function onTimeUpdate() {
  if (!videoRef.value || !videoId.value || result.value?.status !== 'completed') return

  const currentTime = videoRef.value.currentTime
  const frameIndex = Math.min(
    Math.floor(currentTime * videoInfo.value.fps),
    videoInfo.value.total_frames - 1
  )
  currentFrameIndex.value = frameIndex
  getFrameDetections(frameIndex)
}

// ========== 文件选择 ==========
function beforeUpload(fileRaw) {
  file.value = fileRaw
  previewVideoUrl.value = URL.createObjectURL(fileRaw)

  store.videoFile = fileRaw

  // 重置状态
  result.value = null
  rawResultUrl.value = ''
  currentFrameObjects.value = []
  currentFrameIndex.value = -1
  allObjects.value = []
  videoId.value = ''
  progress.value = 0

  return false
}

// ========== 上传并启动轮询 ==========
async function upload() {
  if (!file.value || isPolling.value) return

  try {
    const res = await uploadVideo(file.value)
    result.value = res
    videoId.value = res.video_id
    if (!videoId.value) throw new Error('后端未返回 video_id')

    rawResultUrl.value = `http://localhost:8000${res.result_url}`

    store.videoResult = res
    store.rawResultUrl = rawResultUrl.value
    store.videoId = videoId.value

    startPolling()
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('上传失败，请重试')
  }
}

// ========== 轮询状态 ==========
async function startPolling() {
  if (isPolling.value || !videoId.value) return
  isPolling.value = true

  pollingInterval.value = setInterval(async () => {
    try {
      const statusRes = await getVideoStatus(videoId.value)

      if (statusRes.status === 'processing') {
        progress.value = Math.round((statusRes.progress || 0) * 100)
        result.value = { ...result.value, status: 'processing' }
      } else if (statusRes.status === 'completed') {
        stopPolling()
        progress.value = 100

        let attempts = 0
        const maxAttempts = 5
        const finalUrl = rawResultUrl.value
        while (attempts < maxAttempts && !(await isVideoAccessible(finalUrl))) {
          await new Promise(resolve => setTimeout(resolve, 800))
          attempts++
        }

        result.value = { ...result.value, status: 'completed' }
        await loadVideoObjectsAndInfo()
      } else if (statusRes.status === 'failed') {
        stopPolling()
        ElMessage.error('视频处理失败，请重试')
        result.value = { ...result.value, status: 'failed' }
        progress.value = 0
      }
    } catch (err) {
      console.warn('轮询状态失败:', err)
    }
  }, 1500)
}

function stopPolling() {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
  isPolling.value = false
}

// ========== 加载物体 + 视频信息 ==========
async function loadVideoObjectsAndInfo() {
  if (!videoId.value) return
  try {
    const [objectsRes, detectionsRes] = await Promise.all([
      getVideoObjects(videoId.value),
      getVideoDetections(videoId.value)
    ])

    allObjects.value = objectsRes.objects

    videoInfo.value = detectionsRes.video_info || { fps: 25, total_frames: 0 }

    store.allObjects = allObjects.value
    store.videoInfo = videoInfo.value
  } catch (error) {
    console.error('获取视频元数据失败:', error)
  }
}

// ========== 帧同步 ==========
async function getFrameDetections(frameIndex) {
  if (!videoId.value || frameIndex < 0) return

  try {
    const res = await getVideoDetections(videoId.value, frameIndex)
    currentFrameObjects.value = res.detections || []
  } catch (error) {
    console.error('获取帧检测数据失败:', error)
  }
}

// ========== 清空 & 生命周期 ==========
function clearResult() {
  if (previewVideoUrl.value) {
    URL.revokeObjectURL(previewVideoUrl.value)
    previewVideoUrl.value = ''
  }
  file.value = null
  result.value = null
  rawResultUrl.value = ''
  currentFrameObjects.value = []
  currentFrameIndex.value = -1
  allObjects.value = []
  videoId.value = ''
  progress.value = 0
  stopPolling()

  store.clearVideoResult()
  localStorage.removeItem('videoDetectCache')
}

onMounted(() => {
  // 从 store 恢复已完成的结果（只读展示）
  if (store.videoResult?.status === 'completed' && store.videoId) {
    result.value = store.videoResult
    rawResultUrl.value = store.rawResultUrl
    videoId.value = store.videoId
    allObjects.value = [...store.allObjects]
    videoInfo.value = { ...store.videoInfo }
  }
})

onUnmounted(() => {
  if (previewVideoUrl.value) {
    URL.revokeObjectURL(previewVideoUrl.value)
  }
  stopPolling()
})
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
  background-color: #f0f9ff;
  border: 1px solid #b3d8ff;
  border-radius: 4px;
  padding: 12px;
  margin-bottom: 16px;
  color: #1989fa;
  font-size: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

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

h4 {
  margin: 10px 0 8px 0;
  font-size: 14px;
  color: #606266;
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

.preview-video {
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

.all-objects-section {
  margin-top: 16px;
}

:deep(.el-empty) {
  margin: 60px 0;
}

:deep(.el-table) {
  & .cell {
    padding: 0 4px !important;
  }
  & th,
  & td {
    padding: 4px 0 !important;
  }
}
</style>