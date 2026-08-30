import { Skeleton } from '@/components/ui/Skeleton'
import { useI18n } from '../../lib/i18n'

interface StructureLoadingStateProps {
  message?: string
  className?: string
}

export function StructureLoadingState({ message, className }: StructureLoadingStateProps) {
  const { t } = useI18n()
  return (
    <div
      role="status"
      aria-live="polite"
      className={
        className ??
        'absolute inset-0 z-10 grid content-center gap-3 bg-background/85 p-6'
      }
    >
      <Skeleton className="mx-auto h-5 w-52" />
      <Skeleton className="h-32 w-full" />
      <span className="text-center text-sm text-muted-foreground">
        {message ?? t.viewer.initializing}
      </span>
    </div>
  )
}
