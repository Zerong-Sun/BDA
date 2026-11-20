import { Frame, FramePanel } from '@/components/reui/frame'
import { Skeleton } from '@/components/ui/Skeleton'
import { useI18n } from '../../lib/i18n'

interface StructureViewerFallbackProps {
  height: number | string
}

export function StructureViewerFallback({
  height,
}: StructureViewerFallbackProps) {
  const { t } = useI18n()
  return (
    <Frame
      role="status"
      aria-live="polite"
      className="w-full"
      style={{ height }}
      spacing="sm"
    >
      <FramePanel className="grid h-full content-center gap-3">
        <Skeleton className="mx-auto h-5 w-52" />
        <Skeleton className="h-32 w-full" />
        <span className="text-center text-sm text-muted-foreground">
          {t.viewer.initializing}
        </span>
      </FramePanel>
    </Frame>
  )
}
