import { describe, expect, it } from 'vitest'
import { formatCitation } from './formatCitation'

describe('formatCitation', () => {
  it('formats PDB structure URLs', () => {
    expect(formatCitation('https://www.rcsb.org/structure/3LS4')).toMatchObject({
      label: 'PDB 3LS4',
      href: 'https://www.rcsb.org/structure/3LS4',
    })
  })

  it('formats PubMed URLs and PMID strings', () => {
    expect(formatCitation('https://pubmed.ncbi.nlm.nih.gov/20630472/')).toMatchObject({
      label: 'PMID 20630472',
      href: 'https://pubmed.ncbi.nlm.nih.gov/20630472/',
    })
    expect(formatCitation('PMID: 20630472')).toMatchObject({
      label: 'PMID 20630472',
      href: 'https://pubmed.ncbi.nlm.nih.gov/20630472/',
    })
  })

  it('formats UniProt identifiers and URLs', () => {
    expect(formatCitation('UniProt Q15116')).toMatchObject({
      label: 'UniProt Q15116',
      href: 'https://www.uniprot.org/uniprotkb/Q15116/entry',
    })
    expect(formatCitation('https://www.uniprot.org/uniprotkb/Q15116/entry')).toMatchObject({
      label: 'UniProt Q15116',
      href: 'https://www.uniprot.org/uniprotkb/Q15116/entry',
    })
  })

  it('formats bare DOI values', () => {
    expect(formatCitation('10.1038/nature13404')).toMatchObject({
      label: 'DOI 10.1038/nature13404',
      href: 'https://doi.org/10.1038/nature13404',
    })
  })

  it('uses hostnames for generic URLs', () => {
    expect(formatCitation('https://example.org/path/to/paper')).toMatchObject({
      label: 'example.org',
      href: 'https://example.org/path/to/paper',
    })
  })

  it('keeps plain strings without links', () => {
    expect(formatCitation('internal assay note')).toEqual({
      label: 'internal assay note',
      title: 'internal assay note',
    })
  })
})
