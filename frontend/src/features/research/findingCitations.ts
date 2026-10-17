import { jsonArray, text } from './jsonHelpers'
import { formatCitation } from './formatCitation'
import type { CitationRecord } from './citationMarkers'

export function findingCitationSources(evidence: Record<string, unknown>): string[] {
  return Array.from(new Set(
    [...jsonArray(evidence.sources), ...jsonArray(evidence.source_refs)]
      .map((source) => text(source).trim())
      .filter(Boolean),
  ))
}

export function findingCitationRecords(evidence: Record<string, unknown>): CitationRecord[] {
  const recorded = jsonArray(evidence.citations).filter((item): item is CitationRecord => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
  // Preserve the answer-local order: [cite:N] was assigned before the finding was saved.
  const covered = new Set(recorded.flatMap((citation) => [text(citation.url), text(citation.entity_id), ...jsonArray(citation.reference_ids).map(text)]))
  return [...recorded, ...findingCitationSources(evidence).filter((source) => !covered.has(source)).map((source) => {
    const formatted = formatCitation(source)
    return { entity_id: source, reference_ids: [source], label: formatted.label, url: formatted.href, source_type: 'external_reference' }
  })]
}

export function workspaceCitationRecords(references: readonly Record<string, unknown>[], language: 'zh' | 'en'): CitationRecord[] {
  return references.map((reference) => {
    const metadata = reference.metadata && typeof reference.metadata === 'object' ? reference.metadata as CitationRecord : {}
    const provenance = metadata.content_provenance && typeof metadata.content_provenance === 'object' ? metadata.content_provenance as CitationRecord : {}
    const title = reference.title && typeof reference.title === 'object' ? reference.title as CitationRecord : {}
    return {
      ...provenance, entity_id: reference.document_id, document_id: reference.document_id,
      ref_id: reference.ref_id, reference_ids: [reference.ref_id],
      // Reviewed research packages use R036 in their bibliography and [36] in prose.
      // Preserve that explicit numbering; never infer it from array position.
      bibliography_number: /^R\d+$/.test(text(reference.ref_id)) ? String(Number(text(reference.ref_id).slice(1))) : undefined,
      label: text(title[language]) || text(title.default) || text(reference.ref_id),
      url: reference.url, source_type: 'scientific_literature', review_status: metadata.review_status,
      verification_status: reference.verification_status,
    }
  })
}
