export type StatusTone = 'green' | 'amber' | 'blue' | 'red' | 'neutral'

export function statusTone(status: string): StatusTone {
  const normalized = status.toLowerCase()
  if (
    ['draft', 'pending', 'queued', 'review', 'guided', 'retest', 'hold', 'qc risk', 'warning', 'unreachable'].some(
      (s) => normalized.includes(s),
    )
  ) {
    return 'amber'
  }
  if (
    ['available', 'active', 'validated', 'completed', 'pass', 'connected', 'success', 'anchor', 'order'].some(
      (s) => normalized.includes(s),
    )
  ) {
    return 'green'
  }
  if (['failed', 'fail', 'reject', 'disconnected', 'trash', 'danger'].some((s) => normalized.includes(s))) {
    return 'red'
  }
  if (['running', 'info'].some((s) => normalized.includes(s))) {
    return 'blue'
  }
  if (['offline', 'unavailable', 'restricted', 'not_started', 'not started', 'skipped', 'neutral'].some((s) => normalized.includes(s))) {
    return 'neutral'
  }
  return 'neutral'
}

export function splitStatusLabels(status: string): string[] {
  return status
    .split(/[·,|/]+/)
    .map((part) => part.trim())
    .filter(Boolean)
}
