import { create } from 'zustand'

interface ToastState {
  message: string | null
  tone: 'info' | 'success' | 'error'
  eventId: number
  show: (message: string, tone?: ToastState['tone']) => void
  clear: () => void
}

let dismissTimer: number | null = null

export const useToastStore = create<ToastState>((set) => ({
  message: null,
  tone: 'info',
  eventId: 0,
  show: (message, tone = 'info') => {
    if (dismissTimer !== null) {
      window.clearTimeout(dismissTimer)
    }
    set((state) => ({ message, tone, eventId: state.eventId + 1 }))
    dismissTimer = window.setTimeout(() => {
      set({ message: null })
      dismissTimer = null
    }, 3200)
  },
  clear: () => {
    if (dismissTimer !== null) {
      window.clearTimeout(dismissTimer)
      dismissTimer = null
    }
    set({ message: null })
  },
}))
