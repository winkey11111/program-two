<template>
  <div class="preview-container">
    <el-button @click="$router.back()">返回</el-button>
    <div style="margin-top: 12px;">
      <img :src="imageUrl" alt="预览" style="max-width: 100%; border: 1px solid #ddd;" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const imageUrl = ref('')

onMounted(() => {
  const { id, which } = route.params
  const base = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'
  imageUrl.value = `${base}/records/file/${id}?which=${which}`
})
</script>