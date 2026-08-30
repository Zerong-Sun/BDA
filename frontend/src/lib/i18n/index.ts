import { useAppStore } from '../store/appStore'
import { en } from './en'
import { zh } from './zh'
import { interpolate } from './format'

export function useI18n() {
  const language = useAppStore((s) => s.language)
  const t = language === 'zh' ? zh : en
  const format = (template: string, vars: Record<string, string | number | undefined | null>) =>
    interpolate(template, vars)
  return { t, language, format }
}

export function getTranslations() {
  const language = useAppStore.getState().language
  const t = language === 'zh' ? zh : en
  const format = (template: string, vars: Record<string, string | number | undefined | null>) =>
    interpolate(template, vars)
  return { t, language, format }
}

export { en, zh }
export { interpolate } from './format'
