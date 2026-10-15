import { describe, expect, it } from 'vitest'
import type { ProjectReviewSection } from '../../lib/schemas/research'
import { filterReviewSections } from './reviewReading'

const record = (id: string, content: string, evidence = {}) => ({
  id, project_id: 'p', brief_id: null, finding_type: 'design_strategy', title: id,
  content, evidence, version: 1, created_at: '', updated_at: '', outcome: 'unspecified' as const,
  supersedes_id: null, provenance: {},
})
const sections: ProjectReviewSection[] = [
  { track: 'design_strategy', label: 'Design', status: 'active', items: [record('route', 'A structural proposal', { uncertainty: 'No functional assay', source_refs: ['PMID:12345678'] })] },
  { track: 'functional_validation', label: 'Validation', status: 'active', items: [record('assay', 'Independent controls')] },
  { track: 'custom_history', label: 'History', status: 'active', items: [record('history', 'Retained failure')] },
]
describe('research reading navigation', () => {
  it('retains unknown historical tracks in the full view and does not mutate the record', () => {
    expect(filterReviewSections(sections, 'all', '')).toHaveLength(3)
    expect(filterReviewSections(sections, 'route', '').map(s => s.track)).toEqual(['design_strategy'])
    expect(sections).toHaveLength(3)
  })
  it('searches uncertainties and citations as well as the visible narrative', () => {
    expect(filterReviewSections(sections, 'all', ' functional assay ')[0].items[0].id).toBe('route')
    expect(filterReviewSections(sections, 'all', 'pmid:12345678')[0].items[0].id).toBe('route')
    expect(filterReviewSections(sections, 'validation', 'structural')).toEqual([])
    expect(filterReviewSections(sections, 'all', 'retained failure')[0].track).toBe('custom_history')
  })
})
