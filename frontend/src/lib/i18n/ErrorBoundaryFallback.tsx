import { useI18n } from './index'
import { Alert, AlertDescription, AlertTitle } from '../../components/reui/alert'
import { Button } from '../../components/ui/Button'
import { AppFrame } from '../../components/ui/AppFrame'

interface ErrorBoundaryFallbackProps {
  message?: string
  onReset: () => void
}

export function ErrorBoundaryFallback({ message, onReset }: ErrorBoundaryFallbackProps) {
  const { t } = useI18n()

  return (
    <AppFrame className="mx-auto my-12 max-w-lg" panelClassName="p-4">
      <Alert variant="destructive">
      <AlertTitle>{t.shared.errorBoundaryTitle}</AlertTitle>
      <AlertDescription>{t.shared.errorBoundaryBody}</AlertDescription>
      {message ? (
        <pre className="mb-4 overflow-x-auto rounded-md bg-bg-app p-3 text-xs text-text-secondary">{message}</pre>
      ) : null}
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onReset}
        >
          {t.shared.tryAgain}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => window.location.reload()}
        >
          {t.shared.reloadPage}
        </Button>
      </div>
      </Alert>
    </AppFrame>
  )
}
