import { useEffect } from 'react'
import { useI18n } from '../../lib/i18n'
import { toast } from 'sonner'
import { Toaster } from './sonner'
import { useToastStore } from './toastStore'

export function Toast() {
  const { language } = useI18n()
  const { eventId, message, tone } = useToastStore()

  useEffect(() => {
    if (!message) return
    toast[tone](message, { duration: 3200 })
  }, [eventId, message, tone])

  return <Toaster position="bottom-right" richColors closeButton containerAriaLabel={language === 'zh' ? '通知' : 'Notifications'} toastOptions={{ closeButtonAriaLabel: language === 'zh' ? '关闭通知' : 'Dismiss notification' }} />
}
