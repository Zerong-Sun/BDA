import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { resolve } from 'node:path'

// Resolved against this file's directory, not the working directory. With
// `process.cwd()` the alias became `<repo>/src` whenever vitest ran from the repository
// root, so `npx --prefix frontend vitest run --root frontend <file>` failed on every
// test that imports `@/...` with a misleading "cannot find package".
//
// `import.meta.dirname` rather than `fileURLToPath(import.meta.url)`: this config is
// also imported as a module by `src/test/reuiMigrationAudit.test.ts`, and under vite's
// transform `fileURLToPath` throws on the rewritten url. `import.meta.dirname` is
// correct in both paths - the audit test resolves its own root the same way.
const rootAlias = resolve(import.meta.dirname, 'src')

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
