import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { resolve } from 'node:path'

const rootAlias = resolve(process.cwd(), 'src')

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [{ find: '@', replacement: rootAlias }],
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
