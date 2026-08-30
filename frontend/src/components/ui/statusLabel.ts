import type { TranslationDict } from '../../lib/i18n/types'

export function localizeStatusLabel(raw: string, status: TranslationDict['shared']['status']): string {
  const normalized = raw.trim().toLowerCase().replace(/[\s_-]+/g, '')
  const map: Record<string, keyof TranslationDict['shared']['status']> = {
    notstarted: 'notStarted',
    queued: 'queued',
    running: 'running',
    completed: 'completed',
    done: 'done',
    failed: 'failed',
    locked: 'locked',
    current: 'current',
  }
  const key = map[normalized]
  return key ? status[key] : raw
}
