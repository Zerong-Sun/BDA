import type { Candidate } from '../../lib/schemas/candidate'

/** Serialize actual nested scores, keeping missing values empty and identities explicit. */
export function candidatesCsv(candidates: Candidate[]): string {
  const keys = [...new Set(candidates.flatMap((c) => Object.keys(c.scores)))].sort()
  const header = ['candidate_id', 'candidate_key', 'name', 'status', 'source_dataset', 'sequence', ...keys]
  const cell = (value: unknown): string => {
    if (value === null || value === undefined) return ''
    let text = typeof value === 'object' ? JSON.stringify(value) : String(value)
    if (typeof value === 'string' && /^[=+@\-\t\r]/.test(text)) text = "'" + text
    return '"' + text.replaceAll('"', '""') + '"'
  }
  return '\ufeff' + [header.map(cell).join(','), ...candidates.map((c) => [
    c.id, c.candidate_key, c.name, c.status, c.properties.source_dataset, c.properties.sequence,
    ...keys.map((key) => c.scores[key]),
  ].map(cell).join(','))].join('\r\n') + '\r\n'
}
