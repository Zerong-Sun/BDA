import type { CitationRecord } from './citationMarkers'

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)]))
  }
  return value
}

/** Collapse only identical provenance records; equal titles can be different evidence. */
export function groupCitations(citations: readonly CitationRecord[]) {
  const groups = new Map<string, { citation: CitationRecord; numbers: number[] }>()
  citations.forEach((citation, index) => {
    const key = JSON.stringify(canonical(citation))
    const existing = groups.get(key)
    if (existing) existing.numbers.push(index + 1)
    else groups.set(key, { citation, numbers: [index + 1] })
  })
  return [...groups.values()]
}
