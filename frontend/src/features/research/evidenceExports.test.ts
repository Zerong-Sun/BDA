import { describe, expect, it } from 'vitest'
import { citationBibliography, evidenceAnnotations } from './evidenceExports'
import type { EvidenceNote, LiteratureReference } from './evidenceNotes'

const note: EvidenceNote = {
  id: 'evidence-1', document_id: 'paper-1', document_title: 'A result in mice', argument: 'We should replicate the result', argument_id: 'argument-1',
  paper_claim: 'The authors observed an effect', interpretation: 'A follow-up might distinguish explanations', limitations: 'Not demonstrated in humans',
  relation: 'contradicts', quote: 'The effect was not observed.', locator: 'Results', structured_locator: { page: 5, section: 'Results', figure: 'Fig. 2' },
  source_url: 'https://example.org/paper', anchor_status: 'changed', review_status: 'pending', reviewed_by: null, reviewed_at: null, version: 3,
  created_at: '2026-10-11T00:00:00Z', updated_at: '2026-10-11T00:00:00Z',
  source_ref: { anchor_scope: 'saved_chunk', chunk_id: 'chunk-1', content_checksum_sha256: 'a'.repeat(64), selector: [
    { type: 'TextQuoteSelector', exact: 'The effect was not observed.', prefix: 'Before ', suffix: ' Afterwards' },
    { type: 'TextPositionSelector', start: 7, end: 35 },
  ] },
}
const reference: LiteratureReference = {
  document_id: 'paper-1', title: { default: note.document_title }, ref_id: 'R1', status: 'available',
  authors: 'Collaborative Study Group; Smith J', journal: 'Test journal', year: '2025', doi: '10.1000/test', url: note.source_url,
}

describe('standard citation exports', () => {
  it('exports one publication for consolidated entries while annotation sources keep their own IDs', () => {
    const other = { ...note, id: 'evidence-other', document_id: 'paper-old' }
    const merged = { ...reference, metadata: { consolidated_document_ids: ['paper-old'] } }
    const result = citationBibliography([note, other], [merged])
    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({ id: 'urn:uuid:paper-1', DOI: '10.1000/test' })
    expect(evidenceAnnotations([note, other], 'project-1', true).items[1]['bda:document']).toBe('urn:uuid:paper-old')
  })
  it('exports unique CSL items without inventing author names or publication dates', () => {
    const result = citationBibliography([note, { ...note, id: 'evidence-2' }], [reference])
    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({ type: 'article-journal', author: [{ literal: reference.authors }], issued: { 'date-parts': [[2025]] }, DOI: '10.1000/test' })
    const missing = citationBibliography([note], [])
    expect(missing[0]).not.toHaveProperty('issued')
    expect(missing[0]).not.toHaveProperty('author')
    expect(missing[0].title).toBe(note.document_title)
  })

  it('keeps character offsets scoped to saved text and records uncertainty and partial selection', () => {
    const page = evidenceAnnotations([note], 'project-1', false)
    expect(page['bda:scope']).toBe('shown_evidence_selection')
    expect(page['bda:loadedProjectComplete']).toBe(false)
    const annotation = page.items[0]
    expect(annotation.target.source).toBe('urn:uuid:chunk-1')
    expect(annotation.target.selector).toEqual(note.source_ref.selector)
    expect(annotation['bda:publication']).toBe(note.source_url)
    expect(annotation['bda:anchorStatus']).toBe('changed')
    expect(annotation['bda:relation']).toBe('contradicts')
    expect(annotation.body.find((body) => body['bda:kind'] === 'author_claim')?.value).toBe(note.paper_claim)
    expect(annotation.body.find((body) => body['bda:kind'] === 'project_argument')?.value).toBe(note.argument)
  })

  it('does not apply a local character offset to a publisher URL for a manual excerpt', () => {
    const page = evidenceAnnotations([{ ...note, source_ref: { ...note.source_ref, anchor_scope: 'user_supplied_excerpt' }, anchor_status: 'unverified' }], 'project-1', true)
    expect(page.items[0].target.source).toBe(note.source_url)
    expect(page.items[0].target.selector).toHaveLength(1)
    expect(page.items[0].target.selector[0].type).toBe('TextQuoteSelector')
    expect(page.items[0]['bda:anchorStatus']).toBe('unverified')
  })
})
