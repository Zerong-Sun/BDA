import type { ProjectReviewSection, ResearchFinding } from '../../lib/schemas/research'

export const REVIEW_SECTION_ORDER = [
  'meaning_application',
  'target_mechanism_structure',
  'prior_art_landscape',
  'binding_strategy',
  'design_strategy',
  'purification_plan',
  'functional_validation',
  'developability_risk',
  'success_criteria',
  'references_reading',
  'open_questions_next',
] as const

export type ReviewTrack = (typeof REVIEW_SECTION_ORDER)[number]

export const REVIEW_SECTION_LABELS: Record<ReviewTrack, { en: string; zh: string }> = {
  meaning_application: {
    en: 'Project significance and application',
    zh: '项目意义与应用',
  },
  target_mechanism_structure: {
    en: 'Target mechanism, function, structure, sequence, and hotspots',
    zh: '靶点机制、功能、结构、序列与热点',
  },
  prior_art_landscape: {
    en: 'Prior art, competing approaches and precedents',
    zh: '现有技术、竞争路线与先例',
  },
  binding_strategy: {
    en: 'Binding method and recognition strategy',
    zh: '结合方式与识别策略',
  },
  design_strategy: {
    en: 'Computational design method',
    zh: '计算设计方法',
  },
  purification_plan: {
    en: 'Expression and purification plan',
    zh: '表达与纯化方案',
  },
  functional_validation: {
    en: 'Functional validation plan',
    zh: '功能验证方案',
  },
  developability_risk: {
    en: 'Developability and risk assessment',
    zh: '可开发性与风险评估',
  },
  success_criteria: {
    en: 'Success criteria and Go/No-Go gates',
    zh: '成功标准与推进/终止关口',
  },
  references_reading: {
    en: 'References and reading list',
    zh: '参考文献与阅读清单',
  },
  open_questions_next: {
    en: 'Open questions and next experiments',
    zh: '开放问题与下一步实验',
  },
}

export function isReviewTrack(value: string): value is ReviewTrack {
  return (REVIEW_SECTION_ORDER as readonly string[]).includes(value)
}

export function reviewSectionLabel(track: ReviewTrack, language: 'en' | 'zh'): string {
  return REVIEW_SECTION_LABELS[track][language]
}

/**
 * The API labels review sections in English only, so prefer the local bilingual
 * taxonomy and fall back to the server label for tracks we do not know about.
 */
export function localizedSectionLabel(
  track: string,
  language: 'en' | 'zh',
  fallback: string,
): string {
  return isReviewTrack(track) ? REVIEW_SECTION_LABELS[track][language] : fallback
}

export interface ReviewCompletion {
  percent: number
  completed_sections: number
  total_sections: number
}

/**
 * v2 returns a flat `findings` list rather than pre-grouped review sections, so
 * the review document is assembled client-side: findings are bucketed by
 * `finding_type` (the track), canonical tracks are always rendered in taxonomy
 * order so empty sections still prompt the user, and any unknown server-side
 * track is appended rather than dropped.
 */
export function buildReviewSections(
  findings: readonly ResearchFinding[],
  language: 'en' | 'zh',
): ProjectReviewSection[] {
  const byTrack = new Map<string, ResearchFinding[]>()
  for (const finding of findings) {
    const existing = byTrack.get(finding.finding_type)
    if (existing) existing.push(finding)
    else byTrack.set(finding.finding_type, [finding])
  }
  const extras = [...byTrack.keys()].filter((track) => !isReviewTrack(track)).sort()
  return [...REVIEW_SECTION_ORDER, ...extras].map((track) => {
    const items = byTrack.get(track) ?? []
    return {
      track,
      label: localizedSectionLabel(track, language, track.replaceAll('_', ' ')),
      status: items.length > 0 ? 'complete' : 'empty',
      items,
    }
  })
}

export function reviewCompletion(sections: readonly ProjectReviewSection[]): ReviewCompletion {
  const total = sections.length
  const completed = sections.filter((section) => section.items.length > 0).length
  return {
    percent: total > 0 ? Math.round((completed / total) * 100) : 0,
    completed_sections: completed,
    total_sections: total,
  }
}

export function inferTrackFromText(text: string, language: 'en' | 'zh'): ReviewTrack | undefined {
  const normalized = text.toLowerCase()
  for (const track of REVIEW_SECTION_ORDER) {
    const labels = REVIEW_SECTION_LABELS[track]
    const localizedLabels = language === 'zh' ? [labels.zh, labels.en] : [labels.en, labels.zh]
    const candidates = [...localizedLabels, track.replaceAll('_', ' ')]
    if (candidates.some((label) => normalized.includes(label.toLowerCase()))) {
      return track
    }
  }
  return undefined
}
