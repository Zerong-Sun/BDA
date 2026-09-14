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

// jsdom has no Web Animations API. base-ui's scroll area returns early when
// `ResizeObserver` is missing; with the stub above it continues, and a timer it
// schedules beside the observer calls `viewport.getAnimations()`. That throws
// unhandled, and vitest fails the run on it even though every test passes. No
// animations run in jsdom, so an empty list is the true answer.
//
// Defining it has a second effect: base-ui's popups close synchronously only
// while `getAnimations` is missing, and otherwise wait a frame for exit
// animations. That would turn every "Escape closes it" assertion asynchronous.
// `BASE_UI_ANIMATIONS_DISABLED` is base-ui's own switch for exactly this, and
// restores the synchronous close the suite was written against.
if (!Element.prototype.getAnimations) {
  Object.defineProperty(Element.prototype, 'getAnimations', {
    configurable: true,
    writable: true,
    value: () => [],
  })
}
;(globalThis as { BASE_UI_ANIMATIONS_DISABLED?: boolean }).BASE_UI_ANIMATIONS_DISABLED = true

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
