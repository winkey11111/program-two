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
              v-if="previewVideoUrl || (result?.status === 'completed')"
              ref="videoRef"
              :src="result?.status === 'completed' ? resultUrl : previewVideoUrl"
              controls
              class="preview-video"
              @timeupdate="onTimeUpdate"
              @play="onVideoPlay"
              @pause="onVideoPause"
            ></video>
            <canvas
              v-if="result?.status === 'completed'"
              ref="overlayCanvasRef"
              class="overlay-canvas"
            ></canvas>

            <!-- 占位提示 -->
            <div v-if="!previewVideoUrl && (!result || result.status !== 'completed')" class="empty-placeholder">
              <el-icon class="empty-icon"><VideoCamera /></el-icon>
              <p>{{ file ? '视频处理中…' : '请上传视频' }}</p>
            </div>
          </div>
        </div>

        <!-- 检测结果表格 -->
        <div class="detection-section">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h3>识别结果{{ currentFrameIndex >= 0 ? `（第 ${currentFrameIndex} 帧）` : '' }}</h3>
            <!-- 控制按钮组 -->
            <div class="control-buttons">
              <el-button
                v-if="result?.status === 'completed' && allObjects.length > 0"
                size="small"
                @click="toggleAllBoxes"
              >
                {{ allHidden ? '显示全部' : '隐藏全部' }}
              </el-button>
              <el-button
                v-if="result?.status === 'completed' && allObjects.length > 0"
                size="small"
                @click="resetBoxes"
              >
                重置显示
              </el-button>
            </div>
          </div>
          <div class="inner-frame">
            <div v-if="result?.status === 'completed' && allObjects?.length">
              <el-table
                :data="currentFrameObjects"
                style="width: 100%"
                table-layout="fixed"
                height="300"
              >
                <el-table-column prop="class" label="类别" width="80" />
                <el-table-column label="ID" width="60">
                  <template #default="{ row }">
                    {{ row.id }}
                  </template>
                </el-table-column>
                <el-table-column label="置信度" width="80">
                  <template #default="{ row }">
                    {{ (row.confidence * 100).toFixed(1) }}%
                  </template>
                </el-table-column>
                <el-table-column label="边界框" width="160" show-overflow-tooltip>
                  <template #default="{ row }">
                    {{ row.bbox?.map(v => Math.round(v)).join(', ') }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="80">
                  <template #default="{ row }">
                    <el-switch
                      v-model="row.visible"
                      inline-prompt
                      size="small"
                      active-text="显"
                      inactive-text="隐"
                      @change="(val) => toggleBoxVisibility(row.id, val)"
                    />
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
                  <el-table-column label="ID" width="60">
                    <template #default="{ row }">
                      {{ row.id }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="class" label="类别" width="80" />
                  <el-table-column label="出现次数" width="80">
                    <template #default="{ row }">
                      {{ row.appearances }}
                    </template>
                  </el-table-column>
                  <el-table-column label="首次出现" width="100">
                    <template #default="{ row }">
                      {{ formatTimestamp(row.first_seen) }}
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="80">
                    <template #default="{ row }">
                      <el-switch
                        v-model="row.visible"
                        inline-prompt
                        size="small"
                        active-text="显"
                        inactive-text="隐"
                        @change="(val) => toggleBoxVisibility(row.id, val)"
                      />
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
import { ref, onMounted, onUnmounted } from 'vue'
import { 
  uploadVideo, 
  getVideoDetections, 
  getVideoObjects, 
  toggleVideoBoxes, 
  resetVideoBoxes,
  getVideoStatus
} from '../api'
import { VideoCamera } from '@element-plus/icons-vue'

const file = ref(null)
const previewVideoUrl = ref('') // 本地预览 URL
const result = ref(null)
const resultUrl = ref('')
const videoRef = ref(null)
const overlayCanvasRef = ref(null)
const currentFrameObjects = ref([])
const currentFrameIndex = ref(-1)
const allObjects = ref([])
const hiddenIds = ref([])
const videoId = ref('')
const isVideoPlaying = ref(false)
const allHidden = ref(false)
const pollingInterval = ref(null) // 轮询定时器
const isPolling = ref(false)      // 防止重复轮询

// 监听视频播放事件
function onVideoPlay() {
  isVideoPlaying.value = true
  updateDetectionData()
}

// 监听视频暂停事件
function onVideoPause() {
  isVideoPlaying.value = false
}

// 定期更新检测数据（用于流畅显示）
function updateDetectionData() {
  if (!isVideoPlaying.value) return
  onTimeUpdate()
  setTimeout(updateDetectionData, 200)
}

// 选择文件时创建本地预览
function beforeUpload(fileRaw) {
  file.value = fileRaw
  previewVideoUrl.value = URL.createObjectURL(fileRaw)

  // 重置状态
  result.value = null
  resultUrl.value = ''
  currentFrameObjects.value = []
  currentFrameIndex.value = -1
  allObjects.value = []
  hiddenIds.value = []
  videoId.value = ''
  allHidden.value = false
  isVideoPlaying.value = false

  return false // 阻止自动上传
}

// 上传视频并启动状态轮询
async function upload() {
  if (!file.value || isPolling.value) return

  try {
    const res = await uploadVideo(file.value)
    result.value = res

    // 提取 video_id（更可靠的方式）
    const url = res.result_url // e.g. "/files/result/res_abc123.mp4"
    const match = url?.match(/res_([a-z0-9]+)\.mp4$/)
    if (match) {
      videoId.value = match[1]
    } else {
      throw new Error('无法解析 video_id')
    }

    resultUrl.value = `http://localhost:8000${res.result_url}`

    // 启动轮询（无论 status 是什么，都轮询）
    startPolling()
  } catch (error) {
    console.error('上传失败:', error)
    isPolling.value = false
  }
}

// 加载所有检测物体
async function loadVideoObjects() {
  if (!videoId.value) return
  try {
    const res = await getVideoObjects(videoId.value)
    allObjects.value = res.objects.map(obj => ({
      ...obj,
      visible: true
    }))
    updateHiddenIds()
  } catch (error) {
    console.error('获取物体列表失败:', error)
  }
}

// 启动轮询
function startPolling() {
  if (isPolling.value || !videoId.value) return
  isPolling.value = true

  pollingInterval.value = setInterval(async () => {
    try {
      const statusRes = await getVideoStatus(videoId.value)
      result.value = { ...result.value, status: statusRes.status }

      if (statusRes.status === 'completed') {
        stopPolling()
        await loadVideoObjects() // ✅ 状态完成后再加载物体
      } else if (statusRes.status === 'failed') {
        stopPolling()
        ElMessage.error('视频处理失败，请重试')
      }
      // processing 状态：继续轮询
    } catch (err) {
      console.warn('轮询状态失败:', err)
      // 可选：出错也停止轮询
      // stopPolling()
    }
  }, 1500) // 每1.5秒查一次
}

// 停止轮询
function stopPolling() {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
  isPolling.value = false
}

// 切换单个框可见性
function toggleBoxVisibility(boxId, visible) {
  const obj = allObjects.value.find(o => o.id === boxId)
  if (obj) {
    obj.visible = visible
    updateHiddenIds()
    updateVideoBoxes()
  }
}

// 更新隐藏 ID 列表
function updateHiddenIds() {
  hiddenIds.value = allObjects.value
    .filter(obj => !obj.visible)
    .map(obj => obj.id)
  allHidden.value = hiddenIds.value.length === allObjects.value.length
}

// 通知后端更新视频框（可选，若后端支持动态渲染）
async function updateVideoBoxes() {
  if (!videoId.value) return
  try {
    await toggleVideoBoxes(videoId.value, hiddenIds.value, false)
  } catch (error) {
    console.error('更新视频框失败:', error)
  }
}

// 切换全部显示/隐藏
function toggleAllBoxes() {
  const newValue = !allHidden.value
  allObjects.value.forEach(obj => {
    obj.visible = newValue
  })
  updateHiddenIds()
  updateVideoBoxes()
}

// 重置为全部显示
async function resetBoxes() {
  try {
    await resetVideoBoxes(videoId.value)
    allObjects.value.forEach(obj => {
      obj.visible = true
    })
    updateHiddenIds()
  } catch (error) {
    console.error('重置框显示失败:', error)
  }
}

// 格式化时间戳（秒）
function formatTimestamp(timestamp) {
  return `${timestamp.toFixed(2)}s`
}

// 视频时间更新时获取当前帧检测
function onTimeUpdate() {
  if (!videoRef.value || !videoId.value) return

  const currentTime = videoRef.value.currentTime
  const fps = 25 // 实际应从后端获取，此处假设
  const frameIndex = Math.floor(currentTime * fps)
  currentFrameIndex.value = frameIndex

  getFrameDetections(frameIndex)
}

// 获取指定帧的检测数据
async function getFrameDetections(frameIndex) {
  if (!videoId.value) return
  try {
    const res = await getVideoDetections(videoId.value, frameIndex)
    const visibleDetections = res.detections.filter(d => !hiddenIds.value.includes(d.id))
    currentFrameObjects.value = visibleDetections.map(d => ({
      ...d,
      visible: !hiddenIds.value.includes(d.id)
    }))
  } catch (error) {
    console.error('获取帧检测数据失败:', error)
  }
}

function clearResult() {
  stopPolling() // 👈 新增
  if (previewVideoUrl.value) {
    URL.revokeObjectURL(previewVideoUrl.value)
    previewVideoUrl.value = ''
  }
  file.value = null
  result.value = null
  resultUrl.value = ''
  currentFrameObjects.value = []
  currentFrameIndex.value = -1
  allObjects.value = []
  hiddenIds.value = []
  videoId.value = ''
  allHidden.value = false
  isVideoPlaying.value = false
}

onUnmounted(() => {
  if (videoRef.value) {
    videoRef.value.pause()
  }
  if (previewVideoUrl.value) {
    URL.revokeObjectURL(previewVideoUrl.value)
  }
  stopPolling() // 👈 新增
  isVideoPlaying.value = false
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

.all-objects-section {
  margin-top: 16px;
}

.control-buttons {
  display: flex;
  gap: 8px;
}

:deep(.el-empty) {
  margin: 60px 0;
}

:deep(.el-table) {
  & .cell {
    padding: 0 4px !important;
  }
  
  & th {
    padding: 4px 0 !important;
  }
  
  & td {
    padding: 4px 0 !important;
  }
}
</style>