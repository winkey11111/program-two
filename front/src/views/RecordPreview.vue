<template>
  <div class="record-preview">
    <div v-if="loading" class="loading">
      <el-loading-spinner size="60" />
      <p>加载记录中...</p>
    </div>
    <div v-else-if="error" class="error">
      <el-icon color="#f56c6c"><WarningFilled /></el-icon>
      <span>{{ error }}</span>
    </div>
    <div v-else-if="record" class="file-container">
      <el-page-header content="记录预览" />
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
        <el-icon color="#909399"><InfoFilled /></el-icon>
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
} from '../api' // 确保 api 路径正确
import { 
  WarningFilled, 
  InfoFilled, 
  Loading 
} from '@element-plus/icons-vue'
import { ElImage, ElPageHeader, ElRadioGroup, ElRadio, ElIcon } from 'element-plus'

// 1. 接收路由 props（不变）
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
// 2. 状态变量（不变）
const record = ref(null)
const fileUrl = ref('')
const loading = ref(false)
const error = ref('')
const activeWhich = ref(props.which)

// 🌟 关键修复1：把所有函数移到 watch 之前声明！
// 3. 先定义 constructFileUrl（被 watch 和 onMounted 调用）
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

// 4. 定义 handleWhichChange（被模板调用）
const handleWhichChange = (newWhich) => {
  router.push({
    name: 'RecordPreview',
    params: { id: props.id, which: newWhich }
  })
}

// 5. 定义 handleFileError（被模板调用）
// 🌟 关键修复2：修正 isSource 的依赖（之前误用到了 constructFileUrl 里的变量）
const handleFileError = () => {
  const isSource = props.which === 'source' // 直接从 props 获取，不依赖其他函数
  const fileType = isSource ? '原始' : '处理结果'
  error.value = `${fileType}文件加载失败，请检查文件是否存在`
  console.error(`文件加载失败，URL：`, fileUrl.value)
}

// 6. 最后定义 watch（此时所有函数都已声明，可正常访问）
watch(
  () => props.which,
  (newWhich) => {
    activeWhich.value = newWhich
    constructFileUrl() // 现在能正常访问 constructFileUrl 了
  },
  { immediate: true }
)

// 7. onMounted 放在最后（不变）
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
/* 样式部分完全不变，不用改 */
.record-preview {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.loading {
  text-align: center;
  padding: 80px 0;
  color: #666;
}
.loading p {
  margin-top: 20px;
  font-size: 16px;
}
.error {
  text-align: center;
  padding: 80px 0;
  color: #f56c6c;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.unsupported-type {
  text-align: center;
  padding: 80px 0;
  color: #909399;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
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