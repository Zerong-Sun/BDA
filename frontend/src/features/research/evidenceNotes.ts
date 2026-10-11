import type { EvidenceNoteResponse, EvidenceNoteWrite } from '../../lib/api/generated/types.gen'
import type { NormalizedResearchWorkspace } from '../../lib/api/researchWorkspace'
import { safeCitationUrl } from './citationMarkers'

export type LiteratureReference = NormalizedResearchWorkspace['references'][number]
export type EvidenceNote = EvidenceNoteResponse
export const evidenceRelations = ['supports', 'contradicts', 'context'] as const

export function relationLabel(relation: string, zh: boolean) {
  return ({ supports: zh ? '支持' : 'Supports', contradicts: zh ? '反驳 / 限制' : 'Contradicts / limits', context: zh ? '背景 / 方法' : 'Context / method' })[relation] ?? relation
}

export function referenceUrl(reference: LiteratureReference): string {
  return safeCitationUrl(reference.url)
    ?? (reference.doi ? safeCitationUrl(`https://doi.org/${reference.doi}`) : undefined)
    ?? (reference.pmid ? safeCitationUrl(`https://pubmed.ncbi.nlm.nih.gov/${reference.pmid}/`) : undefined) ?? ''
}

export function noteDraft(note?: EvidenceNote, url = ''): EvidenceNoteWrite {
  const selector = Array.isArray(note?.source_ref.selector) ? note.source_ref.selector as Array<Record<string, unknown>> : []
  const position = selector.find((item) => item.type === 'TextPositionSelector')
  return {
    argument: note?.argument ?? '', paper_claim: note?.paper_claim ?? '', interpretation: note?.interpretation ?? '',
    limitations: note?.limitations ?? '', relation: note?.relation ?? 'supports', quote: note?.quote ?? '',
    chunk_id: typeof note?.source_ref.chunk_id === 'string' ? note.source_ref.chunk_id : null,
    quote_start: typeof position?.start === 'number' ? position.start : null,
    locator: note?.locator ?? '', source_url: note?.source_url ?? url,
  }
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
    `${zh ? '原文位置' : 'Location'}: ${note.locator || (zh ? '未记录' : 'Not recorded')}`,
    `${zh ? '论文观点' : 'Paper claim'}: ${note.paper_claim}`,
    `${zh ? '论据解释' : 'Interpretation'}: ${note.interpretation}`,
    `${zh ? '适用边界' : 'Limits'}: ${note.limitations}`,
    `<!-- evidence_note=${note.id}; version=${note.version}; source=${JSON.stringify(note.source_ref)} -->`,
  ].join('\n\n')).join('\n\n---\n\n')
}
