import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './mocks/handlers'

if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string): MediaQueryList => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  })
}

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

// Testing Library only auto-cleans when vitest runs with `globals: true`, which this
// project does not. Without this, every rendered component stays mounted for the rest of
// the file and React's scheduler can fire work after the jsdom environment is torn down,
// surfacing as "ReferenceError: window is not defined" on slower machines.
afterEach(() => {
  cleanup()
  server.resetHandlers()
})

afterAll(() => server.close())
