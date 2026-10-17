import { resolveStoredText } from '../../lib/i18n/localizedText'

export interface PresentedWorkflow {
  id: string
  name: string
  status: string
  graph: Record<string, unknown>
}

export const routeCategories = {
  design: ['设计方法', 'Design methods'],
  validation: ['验证与比较', 'Validation and comparison'],
  calibration: ['方法校准', 'Method calibration'],
  overview: ['项目总览', 'Project overview'],
  history: ['历史记录', 'Historical records'],
  draft: ['待整理草稿', 'Unclassified drafts'],
} as const

export function routePresentation(run: PresentedWorkflow | undefined): Record<string, unknown> {
  const raw = run?.graph.route_presentation
  return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw as Record<string, unknown> : {}
}

export function workflowRouteName(run: PresentedWorkflow, language: 'en' | 'zh'): string {
  const presentation = routePresentation(run)
  const selected = presentation[language === 'zh' ? 'name' : 'name_en']
  if (typeof selected === 'string' && selected.trim()) return selected
  const localized = run.graph.localized_content as Record<string, unknown> | undefined
  return resolveStoredText(localized?.name, language, run.name || run.id)
}

export function groupWorkflowRoutes(runs: PresentedWorkflow[]) {
  return Object.entries(routeCategories).map(([category, labels]) => ({
    category, labels,
    runs: runs.filter((run) => {
      const value = routePresentation(run).category
      return (typeof value === 'string' && Object.hasOwn(routeCategories, value) ? value : 'draft') === category
    }),
  })).filter((group) => group.runs.length > 0)
}
