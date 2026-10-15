import { describe, expect, it } from 'vitest'
import type { Candidate } from '../../lib/schemas/candidate'
import { candidatesCsv } from './candidatesCsv'
describe('candidatesCsv', () => {
  it('exports nested scores, source and escaped text without inventing missing values', () => {
    const csv = candidatesCsv([{ id: '1', candidate_key: 'seq1', name: '=formula,"x"', status: 'scored',
      scores: { plddt: 93.2, rosetta_interface_dg: -78 }, properties: { source_dataset: 'source', sequence: 'ABC' }
    }, { id: '2', candidate_key: 'seq2', name: 'second', status: 'proposed', scores: {}, properties: {} }] as Candidate[])
    expect(csv).toContain('"plddt","rosetta_interface_dg"')
    expect(csv).toContain('"93.2","-78"')
    expect(csv).toContain('"source","ABC"')
    expect(csv).toContain('"\'=formula,""x"""')
    expect(csv).toContain('"2","seq2","second","proposed",,,,')
  })
})
