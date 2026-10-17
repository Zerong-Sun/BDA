import { describe, expect, it } from 'vitest'
import { groupWorkflowRoutes, workflowRouteName } from './routePresentation'

describe('route presentation', () => {
  it('retains malformed and prototype-named categories as unclassified records', () => {
    const runs = ['toString', '__proto__', 'unknown', null, []].map((category, i) => ({
      id: String(i), name: 'Legacy', status: 'draft', graph: { route_presentation: { category } },
    }))
    expect(groupWorkflowRoutes(runs)).toEqual([{ category: 'draft', labels: ['待整理草稿', 'Unclassified drafts'], runs }])
  })
  it('keeps methods, validation and historical versions separate without dropping legacy records', () => {
    const runs = [
      { id: 'old', name: 'Route A', status: 'running', graph: { route_presentation: { category: 'history', name: '旧方法', name_en: 'Prior method' } } },
      { id: 'current', name: 'Route 1', status: 'draft', graph: { route_presentation: { category: 'design', name: '支架改造', name_en: 'Scaffold engineering' } } },
      { id: 'validation', name: 'Route C', status: 'draft', graph: { route_presentation: { category: 'validation' } } },
      { id: 'legacy', name: 'Untitled', status: 'draft', graph: {} },
    ]
    expect(groupWorkflowRoutes(runs).map((group) => [group.category, group.runs.map((run) => run.id)])).toEqual([
      ['design', ['current']], ['validation', ['validation']], ['history', ['old']], ['draft', ['legacy']],
    ])
    expect(workflowRouteName(runs[1], 'zh')).toBe('支架改造')
    expect(workflowRouteName(runs[1], 'en')).toBe('Scaffold engineering')
    expect(workflowRouteName(runs[3], 'zh')).toBe('Untitled')
    expect(runs[0].status).toBe('running')
  })
})
