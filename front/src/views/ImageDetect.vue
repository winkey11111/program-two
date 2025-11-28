<template>
  <div class="image-detect-container" style="min-height: 640px;">
    <div style="display: flex; justify-content: center; margin-bottom: 12px;">
      <h2 style="margin: 0;">图片识别</h2>
    </div>

    <div class="upload-actions">
      <el-upload
        :before-upload="beforeUpload"
        :show-file-list="false"
        aria-label="选择图片文件"
      >
        <el-button>选择图片</el-button>
      </el-upload>

      <el-button
        type="primary"
        :disabled="!store.imageFile"
        @click="upload"
        class="ml-12"
      >
        上传并识别
      </el-button>
      <el-button @click="store.clearImageResult" class="ml-8">
        清空
      </el-button>
    </div>

    <div class="outer-frame">
      <div class="result-layout">
        <!-- 图像预览区 -->
        <div class="preview-section">
          <h3>图像预览</h3>
          <div class="inner-frame" style="position: relative; overflow: hidden;">
            <img
              v-if="store.originalImageUrl"
              :src="store.originalImageUrl"
              ref="previewImageRef"
              @load="onImageLoad"
              alt="原始图像"
              class="preview-image"
            />
            <canvas
              ref="overlayCanvasRef"
              class="overlay-canvas"
            ></canvas>

            <div v-if="!store.originalImageUrl" class="empty-placeholder">
              <el-icon class="empty-icon"><Picture /></el-icon>
              <p>请上传图片</p>
            </div>
          </div>
        </div>

        <!-- 识别结果表格 -->
        <div class="detection-section">
          <h3>识别结果</h3>
          <div class="inner-frame">
            <div v-if="store.result?.detections?.length">
              <el-table
                :data="store.result.detections"
                style="width: 100%"
                table-layout="fixed"
                @row-click="handleRowClick"
                :row-class-name="getRowClassName"
                height="340"
              >
                <!-- 显示开关列 -->
                <el-table-column width="60" align="center">
                  <template #header>
                    <el-checkbox
                      :model-value="allVisible"
                      :indeterminate="indeterminate"
                      @change="toggleAllVisible"
                    />
                  </template>
                  <template #default="{ row }">
                    <el-checkbox
                      :model-value="row.visible !== false"
                      @change="(val) => toggleVisibility(row, val)"
                    />
                  </template>
                </el-table-column>

                <el-table-column prop="id" label="ID" width="50" />
                <el-table-column prop="class" label="类别" width="100" />
                <el-table-column label="置信度" width="100">
                  <template #default="{ row }">
                    {{ (row.confidence * 100).toFixed(1) }}%
                  </template>
                </el-table-column>
                <el-table-column label="边界框" width="260" show-overflow-tooltip>
                  <template #default="{ row }">
                    {{ row.bbox?.map(v => Math.round(v)).join(', ') }}
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <el-empty v-else description="未检测到目标" />
          </div>
        </div>
      </div>
    </div>

    <!-- 大图预览 -->
    <el-dialog
      v-model="imageDialogVisible"
      title="图片预览"
      :fullscreen="true"
      :show-close="true"
      :close-on-click-modal="true"
    >
      <div class="dialog-image-container">
        <img
          :src="currentImageUrl"
          alt="放大预览"
          class="dialog-image"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { useDetectStore } from '@/stores/detect'
import { uploadImage } from '@/api' // 确保路径正确
import { ElMessage } from 'element-plus'
import { Picture } from '@element-plus/icons-vue'
import { ref, watch, nextTick } from 'vue'

const store = useDetectStore()
const imageDialogVisible = ref(false)
const currentImageUrl = ref('')
const previewImageRef = ref(null)
const overlayCanvasRef = ref(null)
const highlightId = ref(null)

// 全选控制
const allVisible = ref(true)
const indeterminate = ref(false)

// 监听 detections 变化，更新全选状态
watch(
  () => store.result?.detections,
  () => {
    if (!store.result?.detections?.length) {
      allVisible.value = true
      indeterminate.value = false
      return
    }
    const visibleCount = store.result.detections.filter(d => d.visible !== false).length
    const total = store.result.detections.length
    allVisible.value = visibleCount === total
    indeterminate.value = visibleCount > 0 && visibleCount < total
  },
  { deep: true, immediate: true }
)

// 监听 result 变化，重绘 canvas
watch(
  () => store.result,
  () => {
    if (previewImageRef.value?.complete) {
      drawDetections()
    }
  },
  { deep: true }
)

function beforeUpload(fileRaw) {
  store.imageFile = fileRaw
  store.originalImageUrl = URL.createObjectURL(fileRaw)
  store.resultUrl = ''
  store.result = null
  highlightId.value = null
  return false
}

async function upload() {
  if (!store.imageFile) return
  try {
    const data = await uploadImage(store.imageFile)
    store.result = data

    // 确保每个 detection 有 visible 字段（默认 true）
    if (store.result.detections) {
      store.result.detections.forEach(det => {
        if (det.visible == null) det.visible = true
      })
    }

    ElMessage.success('识别成功')
  } catch (error) {
    console.error('识别失败:', error)
    ElMessage.error('识别失败，请重试')
  }
}

function handleImageClick() {
  if (store.originalImageUrl) {
    currentImageUrl.value = store.originalImageUrl
    imageDialogVisible.value = true
  }
}

function onImageLoad() {
  nextTick(() => {
    drawDetections()
  })
}

function drawDetections() {
  const img = previewImageRef.value
  const canvas = overlayCanvasRef.value
  if (!img || !canvas || !store.result?.detections) return

  const ctx = canvas.getContext('2d')
  const naturalWidth = img.naturalWidth
  const naturalHeight = img.naturalHeight

  // 设置 canvas 逻辑尺寸 = 原始图尺寸
  canvas.width = naturalWidth
  canvas.height = naturalHeight

  // 清空画布
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // 绘制每个可见的检测框
  store.result.detections.forEach((det) => {
    const isVisible = det.visible !== false
    if (!isVisible) return

    const [x1, y1, x2, y2] = det.bbox
    const color = `rgb(${det.color?.join(',') || '128,128,128'})`
    const isHighlighted = det.id === highlightId.value

    // 框
    ctx.lineWidth = isHighlighted ? 4 : 2
    ctx.strokeStyle = color
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

    // 标签
    const label = `${det.id}:${det.class} ${Math.round(det.confidence * 100)}%`
    ctx.font = '14px Arial'
    const metrics = ctx.measureText(label)
    const labelWidth = metrics.width
    const labelHeight = 18

    ctx.fillStyle = color
    ctx.fillRect(x1, y1 - labelHeight, labelWidth + 6, labelHeight)

    ctx.fillStyle = '#fff'
    ctx.fillText(label, x1 + 3, y1 - 4)
  })
}

function handleRowClick(row) {
  highlightId.value = row.id
  drawDetections()
}

function getRowClassName({ row }) {
  return row.id === highlightId.value ? 'highlight-row' : ''
}

// 切换单个目标可见性
function toggleVisibility(detection, visible) {
  detection.visible = visible
  drawDetections()

  // 可选：调用后端保存状态
  // if (store.result?.id) {
  //   toggleDetectionVisibility(store.result.id, detection.id, visible)
  // }
}

// 切换全部
function toggleAllVisible(visible) {
  if (store.result?.detections) {
    store.result.detections.forEach(d => {
      d.visible = visible
    })
    drawDetections()
  }
}
</script>

<style scoped>
.image-detect-container {
  padding: 20px;
}

.upload-actions {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.ml-12 {
  margin-left: 12px;
}

.ml-8 {
  margin-left: 8px;
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

.inner-frame {
  width: 100%;
  height: 380px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  box-sizing: border-box;
  background-color: #fff;
  overflow: hidden;
  position: relative;
}

/* 关键：让 img 和 canvas 完全重叠且适配 */
.preview-image,
.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.preview-section .inner-frame:hover {
  border-color: #409eff;
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

/* 高亮行 */
:deep(.highlight-row) {
  background-color: #ecf5ff !important;
}

:deep(.el-table) {
  font-size: 14px;
  border: none;
}

:deep(.el-empty) {
  margin: 60px 0;
}

.dialog-image-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  max-height: 90vh;
  box-sizing: border-box;
}

.dialog-image {
  max-width: 100%;
  max-height: 90vh;
  object-fit: contain;
}

:deep(.el-dialog__body) {
  padding: 0 !important;
}
</style>