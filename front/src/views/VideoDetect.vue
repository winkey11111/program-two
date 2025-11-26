<template>
  <div>
    <h2>视频识别（上传）</h2>
    <el-upload :before-upload="beforeUpload" :show-file-list="false">
      <el-button>选择视频</el-button>
    </el-upload>
    <el-button type="primary" :disabled="!file" @click="upload">上传处理</el-button>

    <div v-if="result">
      <h3>处理状态</h3>
      <p>{{ result.status }}</p>
      <p>预计输出： <a :href="resultUrl" target="_blank">{{ resultUrl }}</a></p>
      <video v-if="videoAvailable" :src="resultUrl" controls style="max-width:90%"></video>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { uploadVideo } from '../api'

const file = ref(null)
const result = ref(null)
const resultUrl = ref("")
const videoAvailable = ref(false)

function beforeUpload(fileRaw) {
  file.value = fileRaw
  return false
}

async function upload() {
  const res = await uploadVideo(file.value)
  result.value = res
  resultUrl.value = `http://localhost:8000${res.result_url}`
  // actual processed video may take time (background). user can refresh history.
}
</script>
