import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

const vendorAlias = (path: string) => fileURLToPath(new URL(path, import.meta.url))
const apiProxyTarget = process.env.BDA_V2_PROXY_TARGET ?? 'http://127.0.0.1:8100'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: [
      { find: '@', replacement: vendorAlias('./src') },
      {
        find: /^h264-mp4-encoder$/,
        replacement: vendorAlias('./src/vendor/h264-mp4-encoder-browser.ts'),
      },
      { find: 'debug/src/browser.js', replacement: vendorAlias('./src/vendor/debug-browser-default.ts') },
      { find: 'debug', replacement: vendorAlias('./src/vendor/debug-browser-default.ts') },
      { find: 'mutative/dist/index.js', replacement: 'mutative/dist/mutative.esm.mjs' },
      { find: 'style-to-js/cjs/index.js', replacement: vendorAlias('./src/vendor/style-to-js-default.ts') },
      { find: 'style-to-js', replacement: vendorAlias('./src/vendor/style-to-js-default.ts') },
    ],
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    // Mol* has circular ESM deps; pre-bundling breaks BuiltInPluginBehaviors.registerDefault.
    exclude: ['molstar'],
  },
  build: {
    chunkSizeWarningLimit: 2000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replaceAll('\\', '/')
          if (!normalized.includes('/node_modules/molstar/')) return undefined
          if (normalized.includes('mol-plugin-ui')) return 'molstar-ui'
          if (normalized.includes('/apps/viewer/') || normalized.includes('mol-plugin')) {
            return 'molstar-plugin'
          }
          if (
            normalized.includes('mol-model') ||
            normalized.includes('mol-math') ||
            normalized.includes('mol-data') ||
            normalized.includes('mol-io')
          ) {
            return 'molstar-model'
          }
          if (
            normalized.includes('mol-canvas3d') ||
            normalized.includes('mol-gl') ||
            normalized.includes('mol-geo') ||
            normalized.includes('mol-repr') ||
            normalized.includes('mol-theme')
          ) {
            return 'molstar-rendering'
          }
          if (normalized.includes('mol-script')) return 'molstar-script'
          const extensionMatch = normalized.match(/\/extensions\/([^/]+)/)
          if (extensionMatch?.[1]) {
            if (extensionMatch[1] === 'anvil') {
              const fileMatch = normalized.match(/\/extensions\/anvil\/([^/.]+)/)
              return `molstar-ext-anvil-${fileMatch?.[1] ?? 'core'}`
            }
            return `molstar-ext-${extensionMatch[1].replace(/[^a-z0-9-]/gi, '-')}`
          }
          return 'molstar-util'
        },
      },
    },
  },
})
