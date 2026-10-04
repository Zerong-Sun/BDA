import { describe, expect, it } from 'vitest'
import { findingCitationSources } from './findingCitations'

describe('findingCitationSources', () => {
  it('includes migrated sources and newer source_refs without duplicates', () => {
    expect(findingCitationSources({
      sources: ['PMID:123', 'https://example.org/article'],
      source_refs: ['PMID:123', 'DOI:10.1000/example'],
    })).toEqual([
      'PMID:123',
      'https://example.org/article',
      'DOI:10.1000/example',
    ])
  })

  it('ignores malformed citation collections', () => {
    expect(findingCitationSources({
      sources: 'not-an-array',
      source_refs: null,
    })).toEqual([])
  })
})

it('keeps answer-local source order when merging legacy references', async () => {
  const { findingCitationRecords } = await import('./findingCitations')
  const citations = [{ entity_id: 'second', reference_ids: ['PMID:2'] }, { entity_id: 'first', reference_ids: ['PMID:1'] }]
  const result = findingCitationRecords({ citations, source_refs: ['PMID:1', 'PMID:3'] })
  expect(result.slice(0, 2)).toEqual(citations)
  expect(result).toHaveLength(3)
  expect(result[2].entity_id).toBe('PMID:3')
})
