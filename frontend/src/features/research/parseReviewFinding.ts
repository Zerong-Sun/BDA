import type { ResearchFindingUpsertPayload } from '../../lib/api/projects'

const URL_PATTERN = /https?:\/\/[^\s)\]>]+/gi
const DOI_PATTERN = /\b10\.\d{4,9}\/[^\s)\]>]+/gi
const PMID_PATTERN = /\bPMID:\s*\d+/gi
const PDB_PATTERN = /\bPDB\s+[A-Z0-9]{4}\b/gi
const UNCERTAINTY_HEADERS = /(?:待验证|开放问题|不确定性|open questions?|uncertainty|still needs verification)[:：]?\s*/i
const ABBREVIATION_PERIOD = /\b(?:E|e|i|vs|Fig|Dr|Mr|Mrs|Ms|St|No|Vol|al|etc)\.\s+/g
const ABBREVIATION_PERIOD_PLACEHOLDER = '∯PERIOD∯'
const TITLE_MAX_CHARS = 160

function firstMeaningfulLine(content: string): string {
  const lines = content
    .split('\n')
    .map((line) => line.replace(/^#+\s*/, '').trim())
    .filter(Boolean)
  return lines[0] ?? 'Copilot synthesis'
}

function trimTitleAtWordBoundary(value: string, maxChars: number): string {
  const trimmed = value.trim()
  if (trimmed.length <= maxChars) return trimmed
  const slice = trimmed.slice(0, maxChars)
  const lastSpace = slice.lastIndexOf(' ')
  if (lastSpace > maxChars * 0.6) return slice.slice(0, lastSpace).trim()
  return slice.trim()
}

export function firstSentenceForTitle(statement: string): string {
  const protectedText = statement.replace(ABBREVIATION_PERIOD, (match) =>
    match.replace('.', ABBREVIATION_PERIOD_PLACEHOLDER),
  )
  const first = protectedText.split(/[.!?。！？]\s+/)[0]?.trim() ?? statement.trim()
  return first.split(ABBREVIATION_PERIOD_PLACEHOLDER).join('.').trim()
}

function extractUncertainty(content: string): string | null {
  const match = content.match(UNCERTAINTY_HEADERS)
  if (!match || match.index === undefined) return null
  const tail = content.slice(match.index + match[0].length).trim()
  const nextSection = tail.search(/\n#{1,3}\s|\n[A-Z][^\n]{0,40}:\s/)
  const slice = nextSection > 0 ? tail.slice(0, nextSection) : tail
  const cleaned = slice.trim()
  return cleaned || null
}

function extractSourceRefs(content: string): string[] {
  const refs = new Set<string>()
  for (const pattern of [URL_PATTERN, DOI_PATTERN, PMID_PATTERN, PDB_PATTERN]) {
    const matches = content.match(pattern) ?? []
    for (const item of matches) refs.add(item.trim())
  }
  return [...refs]
}

export function parseReviewFinding(content: string, track: string): ResearchFindingUpsertPayload {
  const title = trimTitleAtWordBoundary(firstMeaningfulLine(content), TITLE_MAX_CHARS)
  const uncertainty = extractUncertainty(content)
  let statement = content.trim()
  if (statement.startsWith(title)) {
    statement = statement.slice(title.length).trim()
    statement = statement.replace(/^\n+/, '')
  }
  if (!statement) statement = content.trim()

  return {
    finding_type: track,
    title,
    content: statement,
    evidence: { evidence_level: 'copilot_synthesis', source_refs: extractSourceRefs(content),
      uncertainty, review_status: 'pending_review' },
  }
}
