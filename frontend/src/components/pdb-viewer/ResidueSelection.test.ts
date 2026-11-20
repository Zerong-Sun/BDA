import { describe, expect, it } from 'vitest'
import { parseResidueSelection } from './residueSelectionParser'

describe('author-numbered residue selections', () => {
  it('keeps chain and author numbering and removes duplicate requests', () => {
    expect(parseResidueSelection('A:56, B:12 A:56; AA:-1')).toEqual([{ chainId: 'A', seq: 56 }, { chainId: 'B', seq: 12 }, { chainId: 'AA', seq: -1 }])
  })
  it.each(['', 'A56', 'A:56.2', 'A:56oops', 'A:9007199254740993'])('rejects an ambiguous or invalid selection %s', text => {
    expect(() => parseResidueSelection(text)).toThrow()
  })
})
