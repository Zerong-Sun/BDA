import type { GatePolicy, GateSummary } from '../../lib/api/workflowGates'

export type { GatePolicy, GateResult, GateRules, GateSummary } from '../../lib/api/workflowGates'

export const emptyPolicy = (): GatePolicy => ({
  mode: 'automatic',
  configured: false,
  rules: { operator: 'and', conditions: [], descending: true },
})
export function gateLabel(
  policy: GatePolicy | undefined,
  run: GateSummary | undefined,
  zh: boolean,
) {
  if (run) {
    const states: Record<string, string[]> = {
      waiting: ['等待筛选', 'Waiting'],
      evaluating: ['筛选中', 'Screening'],
      awaiting_review: ['待人工选择', 'Awaiting selection'],
      materializing: ['准备筛选文件', 'Preparing subset'],
      empty: ['无合格结果', 'No qualified results'],
      error: ['筛选错误', 'Screening error'],
      previewed: ['试运行完成', 'Preview complete'],
    }
    if (run.status === 'released')
      return `${zh ? '已放行' : 'Released'} ${run.selected} / ${run.total}`
    return states[run.status]?.[zh ? 0 : 1] ?? run.status
  }
  if (policy?.mode === 'dependency') return zh ? '已配置 · 完成依赖' : 'Configured · dependency'
  if (!policy?.configured) return zh ? '待配置门控' : 'Configure gate'
  return zh ? '等待上游' : 'Waiting for upstream'
}
