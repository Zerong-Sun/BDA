import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Toast } from './Toast'
import { useToastStore } from './toastStore'

const sonnerSpies = vi.hoisted(() => ({
  error: vi.fn(),
  info: vi.fn(),
  success: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: sonnerSpies,
  Toaster: () => null,
}))

describe('Toast event bridge', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    sonnerSpies.error.mockClear()
    sonnerSpies.info.mockClear()
    sonnerSpies.success.mockClear()
    useToastStore.getState().clear()
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it('dispatches same-text tone changes and repeated identical events', () => {
    render(<Toast />)

    act(() => useToastStore.getState().show('Saved', 'error'))
    act(() => useToastStore.getState().show('Saved', 'success'))
    act(() => useToastStore.getState().show('Saved', 'success'))

    expect(sonnerSpies.error).toHaveBeenCalledTimes(1)
    expect(sonnerSpies.success).toHaveBeenCalledTimes(2)
  })

  it('restarts the dismissal duration for a repeated identical event', () => {
    act(() => useToastStore.getState().show('Saved', 'success'))
    act(() => vi.advanceTimersByTime(3_000))
    act(() => useToastStore.getState().show('Saved', 'success'))
    act(() => vi.advanceTimersByTime(300))

    expect(useToastStore.getState().message).toBe('Saved')

    act(() => vi.advanceTimersByTime(2_900))
    expect(useToastStore.getState().message).toBeNull()
  })
})
