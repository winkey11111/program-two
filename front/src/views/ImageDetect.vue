<template>
  <div class="image-detect-container">
    <h2 style="text-align: center;">图片识别</h2>

    <div class="upload-actions">
      <el-upload :before-upload="beforeUpload" :show-file-list="false">
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

    <div v-if="store.originalImageUrl || store.resultUrl" class="result-layout">
      <div class="preview-section">
        <h3>图像预览</h3>
        <img
          :src="store.resultUrl || store.originalImageUrl"
          alt="识别结果"
          class="preview-image"
        />
      </div>

      <div class="detection-section">
        <h3>识别结果</h3>
        <div v-if="store.result?.objects?.length">
          <el-table :data="store.result.objects" style="width: 100%">
            <el-table-column prop="class" label="类别" />
            <el-table-column label="置信度" width="100">
              <template #default="{ row }">
                {{ (row.conf * 100).toFixed(1) }}%
              </template>
            </el-table-column>
            <el-table-column label="边界框 (x1,y1,x2,y2)" width="180">
              <template #default="{ row }">
                {{ row.bbox?.map(v => Math.round(v)).join(', ') }}
              </template>
            </el-table-column>
          </el-table>
        </div>
        <el-empty v-else description="未检测到目标" />
      </div>
    </div>

    <div v-else-if="store.originalImageUrl" class="original-preview">
      <h3>原始图像</h3>
      <img :src="store.originalImageUrl" alt="原始图片" class="preview-image" />
    </div>
  </div>
</template>

<script setup>
import { useDetectStore } from '@/stores/detect'
import { uploadImage } from '../api'

const store = useDetectStore()

function beforeUpload(fileRaw) {
  store.imageFile = fileRaw
  store.originalImageUrl = URL.createObjectURL(fileRaw)
  store.resultUrl = ''
  store.result = null
  return false
}

async function upload() {
  if (!store.imageFile) return
  const data = await uploadImage(store.imageFile)
  store.result = data
  store.resultUrl = `http://localhost:8000${data.result_url}`
}
</script>

<style scoped>
.image-detect-container {
  padding: 20px;
}

.upload-actions {
  margin-bottom: 20px;
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

.result-layout {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.preview-section,
.detection-section {
  flex: 1;
  min-width: 300px;
}

.original-preview {
  margin-top: 20px;
}

.preview-image {
  max-width: 100%;
  border: 1px solid #ddd;
  border-radius: 4px;
  display: block;
}

:deep(.el-table) {
  font-size: 14px;
}
</style>
