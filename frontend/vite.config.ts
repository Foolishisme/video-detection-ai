import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // 允许外部访问
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8123', // 后端API地址
        changeOrigin: true,
        secure: false,
        // 如果需要代理到不同的后端地址，可以通过环境变量配置
        // 使用方式：VITE_PROXY_TARGET=http://192.168.1.100:8123 npm run dev
      },
    },
  },
})
