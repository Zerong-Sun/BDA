import type { Project } from '../../lib/schemas/project'
import type { ProjectResearchSummary } from '../../lib/schemas/research'

const MAX_QUERY_TERMS = 10
const STOPWORDS = new Set([
  'project',
  'protein',
  'design',
  'research',
  'analysis',
  'an',
  'a',
  'and',
  'as',
  'by',
  'for',
  'from',
  'in',
  'of',
  'on',
  'or',
  'the',
  'to',
  'with',
  'workflow',
  'route',
  'primary',
  'candidate',
  'candidates',
  'validation',
  'brief',
])

function splitTerms(value: string): string[] {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/[^\p{Letter}\p{Number}.]+/gu, ' ')
    .split(/\s+/)
    .map((term) => term.trim().replace(/^\.+|\.+$/g, ''))
    .filter(Boolean)
}

function compactTerms(...values: Array<string | null | undefined>): string {
  const terms: string[] = []
  const seen = new Set<string>()
  for (const value of values) {
    for (const term of splitTerms(value ?? '')) {
      const key = term.toLowerCase()
      if (/^\d{6,}$/.test(term)) continue
      if (STOPWORDS.has(key) || seen.has(key)) continue
      seen.add(key)
      terms.push(term)
      if (terms.length >= MAX_QUERY_TERMS) return terms.join(' ')
    }
  }
  return terms.join(' ')
}

export function projectKnowledgeQuery(project: Project | null): string {
  return compactTerms(project?.name, project?.summary, project?.project_type)
}

export function projectLiteratureQuery(
  project: Project | null,
  research?: ProjectResearchSummary,
): string {
  const findingText = (research?.findings ?? [])
    .slice(0, 3)
    .map((item) => [item.title, item.content, item.finding_type].join(' '))
    .join(' ')
  return compactTerms(
    research?.brief?.title,
    research?.brief?.content,
    project?.name,
    project?.summary,
    findingText,
  )
}
