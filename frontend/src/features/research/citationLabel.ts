import { citationText, type CitationRecord } from './citationMarkers'

const LANGUAGE_KEYS = new Set(['zh', 'en', 'default'])

function languageRecord(value: unknown): Record<string, string> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  const entries = Object.entries(value)
  return entries.length && entries.every(([key, text]) => LANGUAGE_KEYS.has(key) && typeof text === 'string')
    ? Object.fromEntries(entries) as Record<string, string> : undefined
}

/** Read old Python string-dictionary labels as data. Never evaluate expressions. */
function storedLanguageRecord(value: string): Record<string, string> | undefined {
  if (value.length > 10000 || !value.startsWith('{') || !value.endsWith('}')) return undefined
  try { return languageRecord(JSON.parse(value)) } catch { /* Legacy Python repr below. */ }
  const quoted = String.raw`(?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")`
  const entry = new RegExp(String.raw`\s*(${quoted})\s*:\s*(${quoted})\s*(,|$)`, 'gy')
  const body = value.slice(1, -1).trim()
  const result: Record<string, string> = {}
  let offset = 0
  const decode = (token: string): string | undefined => {
    let valid = true
    const escapes: Record<string, string> = { '\\': '\\', "'": "'", '"': '"', n: '\n', r: '\r', t: '\t' }
    const text = token.slice(1, -1).replace(/\\(.)/g, (_, escaped: string) => {
      if (!(escaped in escapes)) valid = false
      return escapes[escaped] ?? escaped
    })
    return valid ? text : undefined
  }
  while (offset < body.length) {
    entry.lastIndex = offset
    const match = entry.exec(body)
    if (!match) return undefined
    const key = decode(match[1])
    const text = decode(match[2])
    if (!key || !LANGUAGE_KEYS.has(key) || text === undefined || key in result) return undefined
    result[key] = text
    offset = entry.lastIndex
  }
  return languageRecord(result)
}

export function citationLabel(citation: CitationRecord, language: 'zh' | 'en', index: number): string {
  const fallback = citationText(citation.entity_id).trim() || `${language === 'zh' ? '来源' : 'Source'} ${index + 1}`
  const original = citationText(citation.label).trim()
  const localized = languageRecord(citation.label) || storedLanguageRecord(original)
  if (localized) {
    return [localized[language], localized[language === 'zh' ? 'en' : 'zh'], localized.default]
      .find((value) => value?.trim())?.trim() || fallback
  }
  // Other dictionaries are provenance records, not human-readable labels.
  if (original.startsWith('{') && original.endsWith('}')) return fallback
  return original || fallback
}
