import { describe, expect, it } from 'vitest'
import raw from '../../../public/research-packages/pd1-demo-v1.json'
import { BundledResearchPackageSchema, localizedResearchText } from './researchPackage'

describe('bundled PD1 demo research package', () => {
  it('contains one explicitly synthetic PD1 project with closed evidence', () => {
    const bundle = BundledResearchPackageSchema.parse(raw)

    expect(bundle.package_id).toBe('pd1-demo-v1')
    expect(bundle.schema_version).toBe('1.1')
    expect(bundle.license).toBe('CC-BY-4.0')
    expect(bundle.synthetic_demo).toBe(true)
    expect(localizedResearchText(bundle.disclaimer, 'en')).toContain('Do not use')
    expect(bundle.projects.map((project) => project.id)).toEqual(['PD1'])
    expect(bundle.references).toHaveLength(12)
    expect(bundle.edges).toHaveLength(4)
    expect(bundle.candidates).toEqual([])
    expect(bundle.projects[0].structures).toHaveLength(4)
    expect(bundle.projects[0].structures.every((item) => item.url.endsWith('.cif'))).toBe(true)
    expect(Object.fromEntries(bundle.identifiers.map((item) => [item.gene, item.uniprot_accession])))
      .toEqual({ PDCD1: 'Q15116', CD274: 'Q9NZQ7', PTPN6: 'P29350' })
  })

  it('gives PD1 a bilingual review and a closed, visible reference set', () => {
    const bundle = BundledResearchPackageSchema.parse(raw)
    const project = bundle.projects[0]
    const referencesById = new Map(bundle.references.map((reference) => [reference.ref_id, reference]))
    const expectedReferenceIds = new Set(bundle.references.map((reference) => reference.ref_id))
    const bibliographyIds = (review: string) => (
      [...review.matchAll(/^((?:R\d{3}))\.\s/gm)].map((match) => match[1])
    )

    for (const [language, objective, heading] of [
      ['zh', '研究目标', '## 参考文献'],
      ['en', 'Research objective', '## References'],
    ] as const) {
      const review = localizedResearchText(project.project_review, language)
      expect(review).toContain(objective)
      expect(review).toContain(heading)
      expect(new Set(bibliographyIds(review))).toEqual(expectedReferenceIds)
    }

    for (const edge of bundle.edges) {
      expect(referencesById.get(edge.ref_id)?.project_ids).toContain('PD1')
    }
    for (const structure of project.structures) {
      expect(referencesById.get(structure.reference_id)?.project_ids).toContain('PD1')
    }
    expect(bundle.references.every((reference) => reference.project_ids.join() === 'PD1')).toBe(true)
  })

  it('rejects unverified, untraceable, or multiply assigned references', () => {
    const invalidCases = [
      (bundle: typeof raw) => { bundle.references[0].verification_status = 'pending' },
      (bundle: typeof raw) => {
        bundle.references[0].pmid = ''
        bundle.references[0].doi = ''
        bundle.references[0].pubmed_url = ''
        bundle.references[0].doi_url = ''
        bundle.references[0].pmc_url = ''
      },
      (bundle: typeof raw) => { bundle.references[0].project_ids = ['PD1', 'PD1'] },
    ]

    for (const mutate of invalidCases) {
      const bundle = structuredClone(raw)
      mutate(bundle)
      expect(() => BundledResearchPackageSchema.parse(bundle)).toThrow()
    }
  })

  it('rejects broken reference closure and duplicate stable IDs', () => {
    const invalidCases = [
      (bundle: typeof raw) => { bundle.edges[0].ref_id = 'R999' },
      (bundle: typeof raw) => { bundle.projects[0].structures[0].reference_id = 'R999' },
      (bundle: typeof raw) => { bundle.edges[1].claim_id = bundle.edges[0].claim_id },
      (bundle: typeof raw) => { bundle.projects[0].primary_target.pdb_id = '9ZZZ' },
      (bundle: typeof raw) => {
        bundle.projects[0].project_review.zh = bundle.projects[0].project_review.zh.replace('R036.', 'R036:')
      },
      (bundle: typeof raw) => { bundle.synthetic_demo = false },
    ]

    for (const mutate of invalidCases) {
      const bundle = structuredClone(raw)
      mutate(bundle)
      expect(() => BundledResearchPackageSchema.parse(bundle)).toThrow()
    }
  })

  it('accepts the same trusted source URL locator as the backend contract', () => {
    const bundle = structuredClone(raw)
    const reference = bundle.references[0] as typeof bundle.references[0] & {
      source_url?: string
      url?: string
    }
    reference.pmid = ''
    reference.doi = ''
    reference.pubmed_url = ''
    reference.doi_url = ''
    reference.pmc_url = ''
    reference.url = ''
    reference.source_url = 'https://pubmed.ncbi.nlm.nih.gov/41359849/'

    expect(() => BundledResearchPackageSchema.parse(bundle)).not.toThrow()
  })
})
