<template>
  <div>
    <h2>视频识别</h2>
    <el-upload :before-upload="beforeUpload" :show-file-list="false">
      <el-button>选择视频</el-button>
    </el-upload>
    <el-button type="primary" :disabled="!file" @click="upload">上传处理</el-button>

    <div v-if="result">
      <h3>处理状态：{{ result.status }}</h3>

      <!-- 处理完成才显示视频和列表 -->
      <div v-if="result.status === 'completed'">
        <video
          ref="videoRef"
          :src="resultUrl"
          controls
          style="max-width: 90%; margin-top: 12px;"
          @timeupdate="onTimeUpdate"
        ></video>

        <!-- 当前帧检测结果 -->
        <div v-if="currentFrameObjects !== null" style="margin-top: 20px;">
          <h3>当前帧检测目标（第 {{ currentFrameIndex }} 帧）</h3>
          <el-table :data="currentFrameObjects" style="width:100%">
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

        <el-empty v-else style="margin-top: 32px;" description="当前帧无检测目标" />
      </div>

      <p v-else>
        视频正在后台处理中，请稍后刷新或查看<a href="/#/records">历史记录</a>。
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { uploadVideo } from '../api'

const file = ref(null)
const result = ref(null)
const resultUrl = ref("")
const videoRef = ref(null)

// 新增：用于存储每帧数据和当前显示内容
const currentFrameObjects = ref(null)
const currentFrameIndex = ref(-1)

function beforeUpload(fileRaw) {
  file.value = fileRaw
  result.value = null
  currentFrameObjects.value = null
  return false
}

async function upload() {
  const res = await uploadVideo(file.value)
  result.value = res
  resultUrl.value = `http://localhost:8000${res.result_url}`

  // 假设后端在 completed 时返回 frames 字段
  if (res.status === 'completed' && res.frames) {
    // 将 frames 转为 map 或保持数组，这里假设按 frame_index 顺序排列
    // 如果不是，可构建 index -> objects 映射
  }
}

// 视频播放时触发
function onTimeUpdate() {
  if (!videoRef.value || !result.value?.frames) return

  const currentTime = videoRef.value.currentTime // 秒
  const fps = result.value.fps || 30 // 假设后端返回了 fps，否则默认 30
  const frameIndex = Math.floor(currentTime * fps)

  // 防止越界
  if (frameIndex < 0 || frameIndex >= result.value.frames.length) {
    currentFrameObjects.value = null
    currentFrameIndex.value = -1
    return
  }

  const frameData = result.value.frames[frameIndex]
  currentFrameObjects.value = frameData.objects || []
  currentFrameIndex.value = frameIndex
}
</script>