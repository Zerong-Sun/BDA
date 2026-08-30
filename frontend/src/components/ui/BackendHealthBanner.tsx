import { useQuery } from '@tanstack/react-query'
import { WarningIcon } from '@phosphor-icons/react'
import { getHealth } from '../../lib/api/health'
import { useI18n } from '../../lib/i18n'
import { Alert, AlertDescription } from '@/components/reui/alert'

export function BackendHealthBanner() {
  const { t } = useI18n()
  const { isError, isFetched } = useQuery({
    queryKey: ['backend-health'],
    queryFn: getHealth,
    retry: false,
    refetchInterval: 15_000,
    staleTime: 10_000,
  })

  if (!isFetched || !isError) return null

  return (
    <Alert variant="warning" className="rounded-none border-x-0 border-t-0 px-6">
      <WarningIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <AlertDescription>
        {t.shared.backendHealth.messagePrefix}{' '}
        <code className="rounded bg-surface-1 px-1 py-0.5 text-xs text-text-primary">./scripts/dev.sh</code>{' '}
        {t.shared.backendHealth.messageSuffix}
      </AlertDescription>
    </Alert>
  )
}
