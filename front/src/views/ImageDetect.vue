<template>
  <div>
    <h2>图片识别</h2>
    <el-upload :before-upload="beforeUpload" :show-file-list="false">
      <el-button>选择图片</el-button>
    </el-upload>
    <el-button type="primary" :disabled="!file" @click="upload">上传并识别</el-button>

    <div v-if="result">
      <h3>识别结果</h3>
      <img :src="resultUrl" style="max-width:90%;" />
      <pre>{{ result.objects }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { uploadImage } from '../api'

const file = ref(null)
const result = ref(null)
const resultUrl = ref("")

function beforeUpload(fileRaw) {
  file.value = fileRaw
  return false
}

async function upload() {
  if (!file.value) return
  const data = await uploadImage(file.value)
  result.value = data
  resultUrl.value = `http://localhost:8000${data.result_url}`
}
</script>
