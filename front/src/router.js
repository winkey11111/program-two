import { createRouter, createWebHistory } from 'vue-router'
import ImageDetect from './views/ImageDetect.vue'
import VideoDetect from './views/VideoDetect.vue'
import CameraDetect from './views/CameraDetect.vue'
import DetectRecords from './views/DetectRecords.vue'

const routes = [
  { path: '/', component: ImageDetect },
  { path: '/video', component: VideoDetect },
  { path: '/camera', component: CameraDetect },
  { path: '/records', component: DetectRecords }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
