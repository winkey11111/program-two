<template>
  <div class="image-detect-container">
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
        <div class="preview-section">
          <h3>图像预览</h3>
          <div
            class="inner-frame"
            @click="handleImageClick"
            :style="{ cursor: (store.originalImageUrl || store.resultUrl) ? 'pointer' : 'default' }"
          >
            <img
              v-if="store.originalImageUrl || store.resultUrl"
              :src="store.resultUrl || store.originalImageUrl"
              alt="识别结果"
              class="preview-image"
            />
            <div v-else class="empty-placeholder">
              <el-icon class="empty-icon"><Picture /></el-icon>
              <p>请上传图片</p>
            </div>
          </div>
        </div>

        <div class="detection-section">
          <h3>识别结果</h3>
          <div class="inner-frame">
            <div v-if="store.result?.detections?.length">
              <el-table :data="store.result.detections" style="width: 100%" table-layout="fixed">
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
import { uploadImage } from '../api'
import { ElMessage, ElDialog } from 'element-plus'
import { Picture } from '@element-plus/icons-vue'
import { ref } from 'vue'

const store = useDetectStore()
const imageDialogVisible = ref(false)
const currentImageUrl = ref('')

function beforeUpload(fileRaw) {
  store.imageFile = fileRaw
  store.originalImageUrl = URL.createObjectURL(fileRaw)
  store.resultUrl = ''
  store.result = null
  return false
}

async function upload() {
  if (!store.imageFile) return
  try {
    const data = await uploadImage(store.imageFile)
    store.result = data
    store.resultUrl = `http://localhost:8000${data.result_url}`
    ElMessage.success('识别成功')
  } catch (error) {
    console.error('识别失败:', error)
    ElMessage.error('识别失败，请重试')
  }
}

function handleImageClick() {
  if (store.originalImageUrl || store.resultUrl) {
    currentImageUrl.value = store.resultUrl || store.originalImageUrl
    imageDialogVisible.value = true
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
}

.preview-section .inner-frame {
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.preview-section .inner-frame:hover {
  border-color: #409eff;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: all 0.2s;
}

.preview-section .inner-frame:hover .preview-image {
  transform: scale(1.02);
}

.empty-placeholder {
  text-align: center;
  color: #909399;
  padding: 20px;
}

.empty-icon {
  font-size: 36px;
  margin-bottom: 12px;
}

.detection-section .inner-frame {
  overflow-y: auto;
  padding: 10px;
}

:deep(.el-table) {
  font-size: 14px;
  border: none;
  width: 100%;
  table-layout: fixed;
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