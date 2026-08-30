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
