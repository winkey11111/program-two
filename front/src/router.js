// router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import ImageDetect from './views/ImageDetect.vue'
import VideoDetect from './views/VideoDetect.vue'
import CameraDetect from './views/CameraDetect.vue'
import DetectRecords from './views/DetectRecords.vue'
import RecordPreview from './views/RecordPreview.vue'

const routes = [
  { path: '/', component: ImageDetect },
  { path: '/video', component: VideoDetect },
  { path: '/camera', component: CameraDetect },
  { path: '/records', component: DetectRecords },


  {
    path: '/records/:id/:which(result|source)',
    name: 'RecordPreview',
    component: RecordPreview,
    props: true 
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router