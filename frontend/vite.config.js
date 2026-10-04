import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
 
export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [],
      },
    }),
  ],
  optimizeDeps: {
    include: ['framer-motion', '@xyflow/react', 'zustand'],
  },
})