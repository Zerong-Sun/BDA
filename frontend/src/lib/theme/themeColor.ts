import { getThemeColor } from '../../lib/theme/cssVars'

export function themeColor(varName: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const value = getThemeColor(varName)
  return value || fallback
}
