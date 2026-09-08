export interface GateRules {
  operator: 'and' | 'or'
  conditions: Array<{
    metric: string
    op: 'gt' | 'gte' | 'lt' | 'lte' | 'eq' | 'ne'
    value: number
  }>
  sort_metric?: string | null
  descending: boolean
  top_n?: number | null
}
export interface GatePolicy extends Record<string, unknown> {
  mode: 'automatic' | 'manual' | 'review' | 'integrity' | 'dependency'
  configured: boolean
  rules: GateRules
  structure?: {
    preset?: 'multi_helix' | 'structured' | 'beta_sheet'
    min_strands?: number
    chains: string[]
    min_helices: number
    min_helix_length: number
    start?: number | null
    end?: number | null
  } | null
  script_preview_id?: string | null
  script?: string | null
}
export const emptyPolicy = (): GatePolicy => ({
  mode: 'automatic',
  configured: false,
  rules: { operator: 'and', conditions: [], descending: true },
})
export interface GateSummary {
  id: string
  edge_id: string
  status: string
  version: number
  revision: number
  preview: boolean
  total: number
  passed: number
  selected: number
  selected_ids: string[]
  error?: string
  created_at: string
  source_job_id?: string
  released_by?: string
  policy?: GatePolicy
}
export interface GateResult {
  id: string
  key: string
  sequence?: string
  passed: boolean
  needs_attention?: boolean
  selected: boolean
  reasons: string[]
  metrics: Record<string, number>
  files: Array<{ artifact_id: string; port: string; selector: Record<string, unknown> }>
}
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
  if (policy?.mode === 'dependency') return zh ? '等待完成' : 'Wait for completion'
  if (!policy?.configured) return zh ? '待配置门控' : 'Configure gate'
  return zh ? '等待上游' : 'Waiting for upstream'
}
