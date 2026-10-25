import { safeCitationUrl } from './citationMarkers'
import { referenceUrl, referenceDocumentIds, type EvidenceNote, type LiteratureReference } from './evidenceNotes'

/** CSL-JSON bibliographic items only. An authorString stays a literal: do not guess names. */
export function citationBibliography(notes: EvidenceNote[], references: LiteratureReference[]) {
  const seen = new Set<string>()
  return notes.filter((note) => {
    const id = references.find((ref) => referenceDocumentIds(ref).includes(note.document_id))?.document_id ?? note.document_id
    if (seen.has(id)) return false
    seen.add(id)
    return true
  }).map((note) => {
    const ref = references.find((candidate) => referenceDocumentIds(candidate).includes(note.document_id))
    const year = String(ref?.year ?? '')
    const journal = ref?.journal?.trim()
    return {
      id: `urn:uuid:${ref?.document_id ?? note.document_id}`, type: journal ? 'article-journal' : 'article', title: note.document_title,
      URL: (ref ? referenceUrl(ref) : '') || safeCitationUrl(note.source_url),
      ...(ref?.doi ? { DOI: ref.doi.replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '') } : {}),
      ...(ref?.authors?.trim() ? { author: [{ literal: ref.authors.trim() }] } : {}),
      ...(journal ? { 'container-title': journal } : {}),
      ...(/^\d{4}$/.test(year) ? { issued: { 'date-parts': [[Number(year)]] } } : {}),
    }
  })
}

/** W3C Web Annotation page with namespaced BDA assertions and review metadata.
 * Character offsets describe the saved chunk, never the remote publisher page.
 * Imported clients can retain these selectors without treating them as PDF coordinates.
 */
export function evidenceAnnotations(notes: EvidenceNote[], projectId: string, loadedProjectComplete: boolean) {
  return {
    '@context': ['http://www.w3.org/ns/anno.jsonld', { bda: 'urn:bda:evidence:' }],
    type: 'AnnotationPage',
    'bda:project': `urn:uuid:${projectId}`,
    'bda:scope': 'shown_evidence_selection',
    'bda:loadedProjectComplete': loadedProjectComplete,
    items: notes.map((note) => {
      const savedChunk = note.source_ref.anchor_scope === 'saved_chunk' && typeof note.source_ref.chunk_id === 'string'
      const selectors = Array.isArray(note.source_ref.selector) ? note.source_ref.selector as Array<Record<string, unknown>> : []
      const quotes = selectors.filter((selector) => selector.type === 'TextQuoteSelector')
      const quote = quotes.length ? quotes : [{ type: 'TextQuoteSelector', exact: note.quote }]
      return {
        id: `urn:uuid:${note.id}`, type: 'Annotation', motivation: 'commenting',
        created: note.created_at, modified: note.updated_at,
        body: [
          { type: 'TextualBody', purpose: 'commenting', value: note.argument, 'bda:kind': 'project_argument' },
          { type: 'TextualBody', purpose: 'commenting', value: note.paper_claim, 'bda:kind': 'author_claim' },
          { type: 'TextualBody', purpose: 'commenting', value: note.interpretation, 'bda:kind': 'project_interpretation' },
          { type: 'TextualBody', purpose: 'commenting', value: note.limitations, 'bda:kind': 'limitations' },
        ],
        target: {
          type: 'SpecificResource',
          source: savedChunk ? `urn:uuid:${note.source_ref.chunk_id}` : safeCitationUrl(note.source_url),
          selector: savedChunk ? selectors : quote,
        },
        'bda:publication': safeCitationUrl(note.source_url),
        'bda:document': `urn:uuid:${note.document_id}`,
        'bda:argument': note.argument_id ? `urn:uuid:${note.argument_id}` : null,
        'bda:relation': note.relation, 'bda:reviewStatus': note.review_status,
        'bda:anchorStatus': note.anchor_status, 'bda:version': note.version,
        'bda:locator': note.structured_locator ?? { description: note.locator },
        'bda:provenance': note.source_ref,
      }
    }),
  }
}

export function downloadEvidenceFile(content: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const anchor = document.createElement('a')
  anchor.href = url; anchor.download = filename; anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
