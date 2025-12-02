// src/stores/detect.js
import { defineStore } from 'pinia'

export const useDetectStore = defineStore('detect', {
  state: () => ({
    // ========== 图片识别相关状态 ==========
    imageFile: null,
    originalImageUrl: '',
    resultUrl: '',
    result: null,

    // ========== 视频识别相关状态 ==========
    videoFileMeta: null,        // 仅保存文件元信息（name, size, type 等）
    videoId: '',                // 后端返回的唯一视频 ID
    rawResultUrl: '',           // 处理完成后的视频 URL（如 /results/xxx.mp4）
    videoResult: null,          // 完整的上传/处理响应对象（含 status、progress 等）
    allObjects: [],             // 所有检测到的物体（跨帧汇总）
    videoInfo: {                // 视频基础信息
      fps: 25,
      total_frames: 0
    },
    progress: 0                 // 视频处理进度（0~100），专用于视频
  }),

  actions: {
    // 清空图片识别状态（不影响视频）
    clearImageResult() {
      this.imageFile = null
      this.originalImageUrl = ''
      this.resultUrl = ''
      this.result = null
      // ⚠️ 注意：不重置 progress，避免干扰视频状态
    },

    // 清空视频识别状态（含进度）
    clearVideoResult() {
      this.videoFileMeta = null
      this.videoId = ''
      this.rawResultUrl = ''
      this.videoResult = null
      this.allObjects = []
      this.videoInfo = { fps: 25, total_frames: 0 }
      this.progress = 0
    },

    // 清空所有状态
    clearAll() {
      this.clearImageResult()
      this.clearVideoResult()
    }
  },

  // 持久化配置：使用 localStorage 自动保存/恢复指定字段
  persist: {
    key: 'video-detect-cache',
    storage: localStorage,
    paths: [
      // 图片相关（如需持久化可加，当前未用）
      // 'imageFile', 'originalImageUrl', 'resultUrl', 'result',

      // 视频相关（关键字段）
      'videoFileMeta',
      'videoId',
      'rawResultUrl',
      'videoResult',
      'allObjects',
      'videoInfo',
      'progress'
    ]
  }
})