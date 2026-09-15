import { useQuery } from '@tanstack/react-query'
import { WarningIcon } from '@phosphor-icons/react'
import { getHealth } from '../../lib/api/health'
import { ApiError } from '../../lib/api/client'
import { useI18n } from '../../lib/i18n'
import { Alert, AlertDescription } from '@/components/reui/alert'
import { Button } from './Button'

function readinessChecks(error: unknown): Record<string, string> | null {
  if (!(error instanceof ApiError) || error.status !== 503) return null
  const payload = error.payload
  if (!payload || typeof payload !== 'object' || !('checks' in payload)) return null
  const checks = payload.checks
  if (!checks || typeof checks !== 'object' || Array.isArray(checks)) return null
  if (!Object.values(checks).every((value) => typeof value === 'string')) return null
  return checks as Record<string, string>
}

export function BackendHealthBanner() {
  const { t } = useI18n()
  const { isError, isFetched, error, refetch, isFetching } = useQuery({
    queryKey: ['backend-health'],
    queryFn: getHealth,
    retry: false,
    refetchInterval: 15_000,
    staleTime: 10_000,
  })

  if (!isFetched || !isError) return null
  const checks = readinessChecks(error)
  const onlySchedulingPaused = checks?.scheduler_dispatch === 'paused'
    && Object.entries(checks).every(([key, value]) => key === 'scheduler_dispatch' || value === 'ok')
  const onlyWorkersUnavailable = checks?.worker_heartbeats === 'missing'
    && Object.entries(checks).every(([key, value]) => key === 'worker_heartbeats' || value === 'ok')
  const message = onlySchedulingPaused ? t.shared.backendHealth.paused
    : onlyWorkersUnavailable ? t.shared.backendHealth.workersUnavailable
    : checks ? t.shared.backendHealth.degraded : t.shared.backendHealth.unavailable

  return (
    <Alert variant="warning" className="rounded-none border-x-0 border-t-0 px-6">
      <WarningIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <AlertDescription className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>{message}</span>
        <Button type="button" variant="outline" size="sm" disabled={isFetching} onClick={() => void refetch()}>
          {t.shared.apiState.retry}
        </Button>
      </AlertDescription>
    </Alert>
  )
}
