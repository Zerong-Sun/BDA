import type { ProjectReviewSection } from '../../lib/schemas/research'
import { findingCitationSources } from './findingCitations'

export const READING_STAGES = [
  { id: 'question', zh: '科学问题', en: 'Question', tracks: ['meaning_application', 'prior_art_landscape'] },
  { id: 'mechanism', zh: '机制与原理', en: 'Mechanism', tracks: ['target_mechanism_structure', 'binding_strategy'] },
  { id: 'route', zh: '技术路线', en: 'Route', tracks: ['design_strategy', 'purification_plan'] },
  { id: 'validation', zh: '验证与风险', en: 'Validation', tracks: ['functional_validation', 'developability_risk'] },
  { id: 'decision', zh: '判断与下一步', en: 'Next decision', tracks: ['success_criteria', 'open_questions_next'] },
  { id: 'sources', zh: '文献依据', en: 'Sources', tracks: ['references_reading'] },
] as const

export function filterReviewSections(sections: ProjectReviewSection[], stage: string, query: string) {
  const tracks: readonly string[] | undefined = READING_STAGES.find((item) => item.id === stage)?.tracks
  const needle = query.trim().toLocaleLowerCase()
  return sections.filter((section) => !tracks || tracks.includes(section.track)).map((section) => ({
    ...section,
    items: section.items.filter((item) => !needle || [section.label, item.title, item.content,
      typeof item.evidence.uncertainty === 'string' ? item.evidence.uncertainty : '',
      ...findingCitationSources(item.evidence),
    ].join('\n').toLocaleLowerCase().includes(needle)),
  })).filter((section) => section.items.length > 0)
}
