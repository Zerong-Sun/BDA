export const MIN_NODE_WIDTH = 200
export const MAX_NODE_WIDTH = 560

export function workflowNodeWidth(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value)
    ? Math.max(MIN_NODE_WIDTH, Math.min(MAX_NODE_WIDTH, value))
    : undefined
}
