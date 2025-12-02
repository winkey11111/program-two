<template>
  <div class="record-preview">
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <p>加载记录中...</p>
    </div>
    <div v-else-if="error" class="error">
      <span>{{ error }}</span>
    </div>
    <div v-else-if="record" class="file-container">
      <el-page-header title="返回" content="记录预览" @back="goBack" />
      <el-radio-group
        v-model="activeWhich"
        @change="handleWhichChange"
        style="margin-bottom: 20px;"
      >
        <el-radio label="source">原始文件</el-radio>
        <el-radio label="result">处理结果</el-radio>
      </el-radio-group>
      <el-image
        v-if="record.type === 'image' && fileUrl"
        :src="fileUrl"
        fit="contain"
        class="preview-image"
        @error="handleFileError"
        lazy
      >
        <template #error>
          <div class="image-error">图片加载失败</div>
        </template>
      </el-image>
      <video
        v-else-if="record.type === 'video' && fileUrl"
        :src="fileUrl"
        controls
        class="preview-video"
        @error="handleFileError"
        preload="metadata"
      >
        您的浏览器不支持视频播放
      </video>
      <div v-else class="unsupported-type">
        <span>不支持的文件类型：{{ record.type }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getRecord,
  getImageResultUrl,
  getImageSourceUrl,
  getVideoResultUrl,
  getVideoSourceUrl
} from '../api'

// 注意：不再导入任何图标
import { ElImage, ElPageHeader, ElRadioGroup, ElRadio } from 'element-plus'

const props = defineProps({
  id: {
    type: [String, Number],
    required: true,
    validator: val => !!val
  },
  which: {
    type: String,
    required: true,
    validator: val => ['result', 'source'].includes(val)
  }
})

const router = useRouter()
const record = ref(null)
const fileUrl = ref('')
const loading = ref(false)
const error = ref('')
const activeWhich = ref(props.which)

const constructFileUrl = () => {
  if (!record.value) return

  const isSource = props.which === 'source'
  const relativePath = isSource ? record.value.source_url : record.value.result_url

  if (!relativePath) {
    error.value = isSource ? '原始文件路径不存在' : '处理结果路径不存在'
    fileUrl.value = ''
    return
  }

  const filename = relativePath.split('/').pop()
  if (!filename) {
    error.value = '文件名解析失败'
    fileUrl.value = ''
    return
  }

  if (record.value.type === 'image') {
    fileUrl.value = isSource
      ? getImageSourceUrl(filename)
      : getImageResultUrl(filename)
  } else if (record.value.type === 'video') {
    fileUrl.value = isSource
      ? getVideoSourceUrl(filename)
      : getVideoResultUrl(filename)
  } else {
    error.value = `不支持的文件类型：${record.value.type}`
    fileUrl.value = ''
  }
}

const handleWhichChange = (newWhich) => {
  router.push({
    name: 'RecordPreview',
    params: { id: props.id, which: newWhich }
  })
}

const handleFileError = () => {
  const isSource = props.which === 'source'
  const fileType = isSource ? '原始' : '处理结果'
  error.value = `${fileType}文件加载失败，请检查文件是否存在`
  console.error(`文件加载失败，URL：`, fileUrl.value)
}

const goBack = () => {
  router.back()
}

watch(
  () => props.which,
  (newWhich) => {
    activeWhich.value = newWhich
    constructFileUrl()
  },
  { immediate: true }
)

onMounted(async () => {
  loading.value = true
  try {
    const res = await getRecord(props.id)
    if (!res || !res.source_url || !res.type) {
      throw new Error('记录数据格式错误')
    }
    record.value = res
    constructFileUrl()
  } catch (err) {
    console.error('获取记录失败：', err)
    error.value = err.message || '网络错误，无法获取记录'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.record-preview {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

/* 自定义 loading spinner */
.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading {
  text-align: center;
  padding: 80px 0;
  color: #666;
}
.loading p {
  margin-top: 10px;
  font-size: 16px;
}

.error {
  text-align: center;
  padding: 80px 0;
  color: #f56c6c;
  font-size: 16px;
}

.unsupported-type {
  text-align: center;
  padding: 80px 0;
  color: #909399;
  font-size: 16px;
}

.preview-image {
  width: 100%;
  max-height: 600px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.image-error {
  width: 100%;
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  color: #909399;
  border-radius: 8px;
}

.preview-video {
  width: 100%;
  max-height: 600px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  background: #000;
}
</style>