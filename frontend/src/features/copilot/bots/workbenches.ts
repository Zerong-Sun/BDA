/**
 * Where each operator's work lives in this app.
 *
 * The roster itself is served by `/copilot/bots` and is not restated here; what
 * the server cannot know is the frontend's own routes. This is the one mapping
 * from an operator to the pages it works on, so a responsibility page can send
 * the reader to the workbench rather than making them find it in navigation.
 * An operator missing from the map shows no workbench; nothing else depends on it.
 */

export interface Workbench {
  path: string
  tab?: string
  en: string
  zh: string
}

const research = (tab: string, en: string, zh: string): Workbench => ({ path: '/research', tab, en, zh })
const workflow: Workbench = { path: '/workflow', en: 'Workflow', zh: '工作流' }
const decisions: Workbench = { path: '/timeline', en: 'Decision record', zh: '决策记录' }

export const BOT_WORKBENCHES: Readonly<Record<string, readonly Workbench[]>> = {
  conductor: [decisions],
  researcher: [research('goals', 'Goals & questions', '目标与问题'), research('evidence', 'Literature & evidence', '文献与证据'), research('references', 'References', '参考文献'), { path: '/projects', en: 'Project targets', zh: '项目靶点' }],
  planner: [research('structures', 'Structures', '结构'), research('methods', 'Experiment plan', '实验方案'), workflow],
  runner: [workflow],
  analyst: [{ path: '/candidates', en: 'Candidates', zh: '候选分子' }, { path: '/lab', en: 'Lab', zh: '实验台' }, { path: '/results', en: 'Results', zh: '结果' }, decisions],
  auditor: [decisions, workflow],
}

export function workbenchHref(bench: Workbench, projectId: string): string {
  const query = new URLSearchParams({ project: projectId })
  if (bench.tab) query.set('tab', bench.tab)
  return `${bench.path}?${query}`
}

export function botHref(botId: string, projectId: string): string {
  return `/bots/${encodeURIComponent(botId)}?${new URLSearchParams({ project: projectId })}`
}
