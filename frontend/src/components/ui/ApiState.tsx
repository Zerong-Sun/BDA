import type { ReactNode } from 'react'
import { ApiError } from '../../lib/api/client'
import { useI18n } from '../../lib/i18n'
import { Alert, AlertAction, AlertDescription } from '@/components/reui/alert'
import { Button } from './Button'

interface ApiStateProps {
  isLoading?: boolean
  isError?: boolean
  error?: unknown
  loadingMessage?: string
  /** Optional skeleton UI shown while loading instead of the text message. */
  loadingSkeleton?: ReactNode
  emptyMessage?: string
  isEmpty?: boolean
  onRetry?: () => void
  children: ReactNode
}

export function ApiState({
  isLoading,
  isError,
  error,
  loadingMessage,
  loadingSkeleton,
  emptyMessage,
  isEmpty,
  onRetry,
  children,
}: ApiStateProps) {
  const { t } = useI18n()
  const resolvedLoadingMessage = loadingMessage ?? t.shared.apiState.loadingDefault

  if (isLoading) {
    if (loadingSkeleton) {
      return <>{loadingSkeleton}</>
    }
    return (
      <p className="text-sm text-text-secondary" role="status" aria-live="polite">
        {resolvedLoadingMessage}
      </p>
    )
  }

  if (isError) {
    const message = resolveApiErrorMessage(error, t.shared.apiState.backendUnavailable)
    return (
      <Alert variant="destructive" aria-live="assertive">
        <AlertDescription>{message}</AlertDescription>
        {onRetry ? (
          <AlertAction>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetry}
          >
            {t.shared.apiState.retry}
          </Button>
          </AlertAction>
        ) : null}
      </Alert>
    )
  }

  if (isEmpty && emptyMessage) {
    return <p className="text-sm text-text-secondary">{emptyMessage}</p>
  }

  return <>{children}</>
}

function resolveApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error && error.message) return error.message
  return fallback
}
