export type SupportedLanguage = 'en' | 'zh'

/**
 * Resolve only text that is already stored by the application or research
 * package. This helper never creates or requests a translation.
 */
export function resolveStoredText(
  value: unknown,
  language: SupportedLanguage,
  original = '',
): string {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const localized = value as Record<string, unknown>
    const selected = localized[language]
    if (typeof selected === 'string' && selected.trim()) return selected.trim()

    const defaultValue = localized.default
    if (typeof defaultValue === 'string' && defaultValue.trim()) return defaultValue.trim()
  }

  if (original.trim()) return original.trim()

  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const localized = value as Record<string, unknown>
    const alternate = localized[language === 'en' ? 'zh' : 'en']
    if (typeof alternate === 'string' && alternate.trim()) return alternate.trim()
  }

  return typeof value === 'string' ? value.trim() : ''
}
