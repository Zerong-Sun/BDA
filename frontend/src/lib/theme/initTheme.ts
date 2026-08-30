import type { ThemePreference } from '../store/appStore'

export type ResolvedTheme = 'light' | 'dark'

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return preference
}

export function applyTheme(resolved: ResolvedTheme) {
  document.documentElement.setAttribute('data-theme', resolved)
  document.documentElement.classList.toggle('dark', resolved === 'dark')
}

export function initTheme(preference: ThemePreference) {
  applyTheme(resolveTheme(preference))
}

export function watchSystemTheme(onChange: (resolved: ResolvedTheme) => void) {
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const handler = () => onChange(media.matches ? 'dark' : 'light')
  media.addEventListener('change', handler)
  return () => media.removeEventListener('change', handler)
}
