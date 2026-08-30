export function text(value: unknown) {
  return typeof value === 'string' ? value : ''
}

export function jsonRecord(value: unknown): Record<string, unknown> {
  if (!value) return {}
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : {}
    } catch {
      return {}
    }
  }
  return typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

export function jsonArray(value: unknown): unknown[] {
  if (Array.isArray(value)) return value
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
}

export function sourceUrl(source: string, refs: string[]): string | null {
  if (source.startsWith('http')) return source
  const hit = refs.find((ref) => ref.includes(source) || source.includes(ref))
  return hit?.startsWith('http') ? hit : null
}

export function claimTitle(item: Record<string, unknown>) {
  // v2 claims carry their display metadata under `attributes`; documents expose a
  // plain `title`. `context_json` is retained for pre-v2 payloads.
  return (
    text(jsonRecord(item.attributes).title) ||
    text(jsonRecord(item.context_json).title) ||
    text(item.title)
  )
}

export function currentRole() {
  try {
    const raw = sessionStorage.getItem('bda_user')
    return raw ? text((JSON.parse(raw) as { role?: unknown }).role) : ''
  } catch {
    return ''
  }
}

export function commaList(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}
