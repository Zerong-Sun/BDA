import { Cube } from '@phosphor-icons/react'
import { Frame, FramePanel } from '@/components/reui/frame'
import { useI18n } from '../../lib/i18n'

interface StructureEmptyStateProps {
  message?: string
  className?: string
}

export function StructureEmptyState({ message, className }: StructureEmptyStateProps) {
  const { t } = useI18n()
  return (
    <Frame
      className={
        className ??
        'absolute inset-3 flex items-center justify-center'
      }
    >
      <FramePanel className="flex flex-col items-center justify-center gap-2 text-center">
        <Cube className="size-6 text-primary" aria-hidden="true" />
        <p className="max-w-md text-sm text-muted-foreground">
          {message ?? t.viewer.uploadOrSelectHint}
        </p>
      </FramePanel>
    </Frame>
  )
}
