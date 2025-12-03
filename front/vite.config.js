// vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src') 
    }
  },
//  server: {
//    proxy: {
//      '/api': 'http://192.168.8.101:8000',
//      '/files': 'http://192.168.8.101:8000'
//    }
//  }
  server: {
  proxy: {
    "/api": "https://nonintellectually-subsonic-kai.ngrok-free.dev",
    "/files": "https://nonintellectually-subsonic-kai.ngrok.dev"
  }
}
})