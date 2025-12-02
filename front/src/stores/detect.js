import { defineStore } from 'pinia'

export const useDetectStore = defineStore('detect', {
  state: () => ({
    imageFile: null,
    originalImageUrl: '',
    resultUrl: '',
    result: null,
  }),

  actions: {
    clearImageResult() {
      this.imageFile = null
      this.originalImageUrl = ''
      this.resultUrl = ''
      this.result = null
    }
  }
})