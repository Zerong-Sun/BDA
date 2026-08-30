export type ResearchTab =
  | 'goals'
  | 'evidence'
  | 'references'
  | 'structures'
  | 'data'
  | 'methods'
  | 'timeline'
export type LibraryMode = 'literature' | 'knowledge'

export const RESEARCH_TABS: readonly ResearchTab[] = [
  // The goal tree reads first: it is the question the other views answer. It is not the
  // default landing tab, because a bookmark with no ?tab= predates it and should keep
  // opening what it used to open.
  'goals',
  'evidence',
  'references',
  'structures',
  'data',
  'methods',
  // The reasoning timeline reads last on purpose: it is the record of how the other
  // four tabs came to say what they say.
  'timeline',
]

const LEGACY_TAB_ALIASES: Readonly<Record<string, ResearchTab>> = {
  atlas: 'evidence',
  'review-map': 'evidence',
  review: 'evidence',
  target: 'structures',
  library: 'data',
  knowledge: 'data',
  literature: 'references',
}

function asText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

export function normalizeResearchTab(tab: string | null | undefined): ResearchTab {
  const value = asText(tab)
  if ((RESEARCH_TABS as readonly string[]).includes(value)) return value as ResearchTab
  return LEGACY_TAB_ALIASES[value] ?? 'evidence'
}

/**
 * Renders a backend status/stage token in the active language, falling back to
 * a readable version of unknown future values.
 */
export function localizeToken(
  value: string | null | undefined,
  dictionary: Record<string, string>,
): string {
  const token = asText(value)
  if (!token) return ''
  return dictionary[token] ?? token.replaceAll('_', ' ')
}

export function shouldAllowTargetEvidenceReview(stage: string | null | undefined): boolean {
  return stage === 'collecting_evidence' || stage === 'evidence_review'
}

export function shouldAllowLiteratureReview(role: string | null | undefined): boolean {
  return role === 'admin' || role === 'researcher'
}

export function shouldOfferReviewPromotion(status: string | null | undefined): boolean {
  return status === 'accepted' || status === 'confirmed'
}

export function shouldTruncateReviewStatement(statement: string): boolean {
  const trimmed = statement.trim()
  if (!trimmed) return false
  return trimmed.length > 720 || trimmed.split('\n').length > 12
}

export function buildTargetEvidenceReviewContent(item: Record<string, unknown>): string {
  const title = asText(item.title) || 'Target evidence'
  const claim = asText(item.claim)
  const excerpt = asText(item.excerpt)
  const identifier = asText(item.identifier)
  const url = asText(item.url)
  const evidenceLevel = asText(item.evidence_level)
  const sourceType = asText(item.source_type)

  return [
    `## ${title}`,
    claim,
    evidenceLevel ? `Evidence level: ${evidenceLevel}` : '',
    sourceType ? `Source type: ${sourceType}` : '',
    excerpt ? `Quoted evidence: ${excerpt}` : '',
    identifier ? `Identifier: ${identifier}` : '',
    url,
  ]
    .filter(Boolean)
    .join('\n\n')
}

export function buildLiteratureClaimReviewContent(item: {
  claim?: unknown
  confidence?: unknown
  review_status?: unknown
  document_id?: unknown
}): string {
  const statement = asText(item.claim)
  const confidence = asText(item.confidence)
  const reviewStatus = asText(item.review_status)
  const documentId = asText(item.document_id)

  return [
    '## Literature claim',
    statement,
    confidence ? `Confidence: ${confidence}` : '',
    reviewStatus ? `Review status: ${reviewStatus}` : '',
    documentId ? `Document: ${documentId}` : '',
  ]
    .filter(Boolean)
    .join('\n\n')
}
