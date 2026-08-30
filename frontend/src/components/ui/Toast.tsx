import { useEffect } from 'react'
import { toast } from 'sonner'
import { Toaster } from './sonner'
import { useToastStore } from './toastStore'

export function Toast() {
  const { eventId, message, tone } = useToastStore()

  useEffect(() => {
    if (!message) return
    toast[tone](message, { duration: 3200 })
  }, [eventId, message, tone])

  return <Toaster position="bottom-right" richColors />
}
