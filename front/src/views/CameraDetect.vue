<template>
  <div>
    <h2>摄像头识别</h2>

    <div>
      <video ref="localVideo" autoplay playsinline style="width:600px;height:auto;border:1px solid #ccc"></video>
    </div>

    <div style="margin-top:8px">
      <el-button type="primary" @click="startCamera" :disabled="streaming">打开摄像头</el-button>
      <el-button @click="stopCamera" :disabled="!streaming">关闭摄像头</el-button>
      <el-button type="success" @click="captureFrame" :disabled="!streaming">抓拍并识别</el-button>
      <el-button type="warning" @click="startRecording" :disabled="!streaming || recording">开始录制片段</el-button>
      <el-button type="danger" @click="stopRecording" :disabled="!recording">停止并上传片段</el-button>
    </div>

    <div v-if="lastResult" style="margin-top:12px">
      <h3>最后一次抓拍识别</h3>
      <img :src="lastResultUrl" style="max-width:90%"/>
      <pre>{{ lastResult.objects }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { postCameraFrame, saveCameraClip } from '../api'

const localVideo = ref(null)
const streamRef = ref(null)
const streaming = ref(false)
const lastResult = ref(null)
const lastResultUrl = ref("")
let mediaRecorder = null
let recordedBlobs = []
const recording = ref(false)

async function startCamera(){
  try{
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    streamRef.value = stream
    localVideo.value.srcObject = stream
    streaming.value = true
  }catch(e){
    alert("无法打开摄像头: " + e.message)
  }
}

function stopCamera(){
  if(streamRef.value){
    streamRef.value.getTracks().forEach(t => t.stop())
    streamRef.value = null
    streaming.value = false
  }
}

function captureFrame(){
  const video = localVideo.value
  const canvas = document.createElement("canvas")
  canvas.width = video.videoWidth || 640
  canvas.height = video.videoHeight || 480
  const ctx = canvas.getContext("2d")
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
  canvas.toBlob(async (blob) => {
    const res = await postCameraFrame(blob, "frame.jpg")
    lastResult.value = res
    lastResultUrl.value = `http://localhost:8000${res.result_url}`
  }, "image/jpeg", 0.9)
}

function startRecording(){
  recordedBlobs = []
  const options = { mimeType: 'video/webm;codecs=vp9' }
  try{
    mediaRecorder = new MediaRecorder(streamRef.value, options)
  }catch(e){
    mediaRecorder = new MediaRecorder(streamRef.value)
  }
  mediaRecorder.ondataavailable = (e) => {
    if(e.data && e.data.size>0) recordedBlobs.push(e.data)
  }
  mediaRecorder.start()
  recording.value = true
}

async function stopRecording(){
  mediaRecorder.stop()
  recording.value = false
  const blob = new Blob(recordedBlobs, { type: 'video/webm' })
  // upload to backend camera/save
  const res = await saveCameraClip(blob)
  alert("已上传片段，ID: " + res.id)
}
</script>
