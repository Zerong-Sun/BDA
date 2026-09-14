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

// jsdom implements neither of these. `ResizeObserver` is reached by cmdk (the
// command palette) and by anything that measures itself; the guard and
// `configurable` matter because `StructureViewer.test.tsx` installs its own
// inspectable double over this one, and a non-configurable property would make
// that redefinition throw.
if (!globalThis.ResizeObserver) {
  Object.defineProperty(globalThis, 'ResizeObserver', {
    configurable: true,
    writable: true,
    value: class {
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    },
  })
}

// jsdom does not implement this either, and cmdk calls it on the selected
// command-palette item. Guarded like the rest: `TourOverlay.test.tsx` saves and
// restores `HTMLElement.prototype.scrollIntoView`, so defining it
// unconditionally would fight that file's teardown.
if (!HTMLElement.prototype.scrollIntoView) {
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    writable: true,
    value: () => undefined,
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
