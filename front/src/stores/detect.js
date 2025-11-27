// stores/detect.js
import { defineStore } from 'pinia'

export const useDetectStore = defineStore('detect', {
  state: () => ({
    // 图片识别相关状态
    imageFile: null,
    originalImageUrl: '',
    resultUrl: '',
    result: null,

    // 可扩展：视频、摄像头状态...
  }),

  actions: {
    // 清空图片识别状态
    clearImageResult() {
      this.imageFile = null
      this.originalImageUrl = ''
      this.resultUrl = ''
      this.result = null
    }
  }
})