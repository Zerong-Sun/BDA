import type { EvidenceNoteResponse, EvidenceNoteWrite } from '../../lib/api/generated/types.gen'
import type { NormalizedResearchWorkspace } from '../../lib/api/researchWorkspace'
import { safeCitationUrl } from './citationMarkers'

export type LiteratureReference = NormalizedResearchWorkspace['references'][number]
export type EvidenceNote = EvidenceNoteResponse
export type EvidenceDraft = EvidenceNoteWrite
export type ArgumentChoice = { id?: string | null; argument: string }
export const evidenceRelations = ['supports', 'contradicts', 'context'] as const

export const referenceScopes = ['core', 'method', 'context', 'excluded', 'unreviewed'] as const
export type ReferenceScope = typeof referenceScopes[number]

export function referenceDocumentIds(reference: LiteratureReference): string[] {
  const aliases = reference.metadata?.consolidated_document_ids
  return [reference.document_id, ...(Array.isArray(aliases) ? aliases.filter((id): id is string => typeof id === 'string') : [])]
}

export function referenceCuration(reference: LiteratureReference, projectId: string): { scope: ReferenceScope; reason: string } {
  const raw = reference.metadata?.evidence_curation
  if (!raw && reference.metadata?.project_scope_status === 'excluded') return {
    scope: 'excluded', reason: String(reference.metadata.project_scope_reason || ''),
  }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { scope: 'unreviewed', reason: '' }
  const value = raw as Record<string, unknown>
  if (value.project_id !== projectId) return { scope: 'excluded', reason: 'Project attribution mismatch' }
  return {
    scope: referenceScopes.includes(value.scope as ReferenceScope) ? value.scope as ReferenceScope : 'unreviewed',
    reason: typeof value.reason === 'string' ? value.reason : '',
  }
}

export function referenceScopeLabel(scope: ReferenceScope, zh: boolean): string {
  return ({ core: zh ? '直接证据' : 'Direct evidence', method: zh ? '方法参考' : 'Methods', context: zh ? '旁支背景' : 'Related background', excluded: zh ? '已排除' : 'Excluded', unreviewed: zh ? '待核定' : 'Unclassified' })[scope]
}

export function relationLabel(relation: string, zh: boolean) {
  return ({ supports: zh ? '支持' : 'Supports', contradicts: zh ? '反驳 / 限制' : 'Contradicts / limits', context: zh ? '背景 / 方法' : 'Context / method' })[relation] ?? relation
}

export function referenceUrl(reference: LiteratureReference): string {
  return safeCitationUrl(reference.url)
    ?? (reference.doi ? safeCitationUrl(`https://doi.org/${reference.doi}`) : undefined)
    ?? (reference.pmid ? safeCitationUrl(`https://pubmed.ncbi.nlm.nih.gov/${reference.pmid}/`) : undefined) ?? ''
}

export function noteDraft(note?: EvidenceNote, url = ''): EvidenceDraft {
  const selector = Array.isArray(note?.source_ref.selector) ? note.source_ref.selector as Array<Record<string, unknown>> : []
  const position = selector.find((item) => item.type === 'TextPositionSelector')
  return {
    argument: note?.argument ?? '', argument_id: note?.argument_id ?? null,
    structured_locator: note?.structured_locator ?? null,
    paper_claim: note?.paper_claim ?? '', interpretation: note?.interpretation ?? '',
    limitations: note?.limitations ?? '', relation: note?.relation ?? 'supports', quote: note?.quote ?? '',
    chunk_id: typeof note?.source_ref.chunk_id === 'string' ? note.source_ref.chunk_id : null,
    quote_start: typeof position?.start === 'number' ? position.start : null,
    locator: note?.locator ?? '', source_url: note?.source_url ?? url,
  }
}

export function argumentKey(note: EvidenceNote): string {
  return note.argument_id ?? `legacy:${note.argument.trim()}`
}

export function noteMatches(note: EvidenceNote, query: string): boolean {
  return [note.argument, note.paper_claim, note.interpretation, note.limitations, note.quote, note.document_title, note.locator]
    .join(' ').toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
}

/** Export only the loaded selection. No inferred citations or upgraded review status. */
export function evidenceMarkdown(notes: EvidenceNote[], zh: boolean): string {
  return notes.map((note) => [
    `## ${note.argument}`, `**${relationLabel(note.relation, zh)}** · ${note.review_status} · ${note.anchor_status}`,
    `[${note.document_title}](${safeCitationUrl(note.source_url) ?? ''})`,
    `> ${note.quote.replaceAll('\n', '\n> ')}`,
    `${zh ? '原文位置' : 'Location'}: ${[note.locator, note.structured_locator?.section, note.structured_locator?.figure, note.structured_locator?.page ? `p. ${note.structured_locator.page}` : ''].filter(Boolean).join(' · ') || (zh ? '未记录' : 'Not recorded')}`,
    `${zh ? '论文观点' : 'Paper claim'}: ${note.paper_claim}`,
    `${zh ? '论据解释' : 'Interpretation'}: ${note.interpretation}`,
    `${zh ? '适用边界' : 'Limits'}: ${note.limitations}`,
    `<!-- evidence_note=${note.id}; argument_id=${note.argument_id ?? 'legacy'}; version=${note.version}; source=${JSON.stringify(note.source_ref)} -->`,
  ].join('\n\n')).join('\n\n---\n\n')
}
