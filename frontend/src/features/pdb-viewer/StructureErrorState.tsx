import { WarningCircle } from '@phosphor-icons/react'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/reui/alert'
import { Frame, FramePanel } from '@/components/reui/frame'
import { Button } from '@/components/ui/Button'
import { useI18n } from '../../lib/i18n'

interface StructureErrorStateProps {
  error: string
  title?: string
  onRetry?: () => void
  className?: string
  inline?: boolean
}

export function StructureErrorState({
  error,
  title,
  onRetry,
  className,
  inline = true,
}: StructureErrorStateProps) {
  if (!inline) {
    return (
      <Frame
        className={
          className ??
          'flex h-full min-h-[12rem] items-center justify-center'
        }
      >
        <FramePanel className="flex items-center justify-center p-4">
          <StructureAlert error={error} title={title} onRetry={onRetry} />
        </FramePanel>
      </Frame>
    )
  }

  return (
    <div
      className={
        className ??
        'absolute bottom-2 left-2 right-2 z-20'
      }
    >
      <StructureAlert error={error} title={title} onRetry={onRetry} />
    </div>
  )
}

function StructureAlert({
  error,
  title,
  onRetry,
}: Pick<StructureErrorStateProps, 'error' | 'title' | 'onRetry'>) {
  const { t } = useI18n()
  return (
    <Alert variant="destructive">
      <WarningCircle aria-hidden="true" />
      <AlertTitle>{title ?? t.viewer.fetchErrorTitle}</AlertTitle>
      <AlertDescription>{error}</AlertDescription>
      {onRetry ? (
        <AlertAction>
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            {t.viewer.retry}
          </Button>
        </AlertAction>
      ) : null}
    </Alert>
  )
}
