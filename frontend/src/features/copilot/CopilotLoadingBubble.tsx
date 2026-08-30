import { Skeleton } from '../../components/ui/Skeleton'
import { Frame, FramePanel } from '../../components/reui/frame'
import { useI18n } from '../../lib/i18n'
import type { CopilotLoadingStage } from './useCopilotChat'

function ConnectingDots() {
  return (
    <span className="inline-flex items-center gap-1" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="size-1.5 animate-bounce rounded-full bg-primary motion-reduce:animate-none"
          style={{ animationDelay: `${index * 150}ms` }}
        />
      ))}
    </span>
  )
}

function StreamingCursor() {
  return (
    <span className="inline-flex items-center text-primary" aria-hidden="true">
      <span className="h-4 w-0.5 animate-pulse bg-primary motion-reduce:animate-none" />
    </span>
  )
}

interface CopilotLoadingBubbleProps {
  stage: Exclude<CopilotLoadingStage, 'idle'>
  detail?: string | null
  compact?: boolean
}

export function CopilotLoadingBubble({
  stage,
  detail,
  compact = false,
}: CopilotLoadingBubbleProps) {
  const { t, format } = useI18n()
  const label =
    stage === 'connecting'
      ? t.copilot.loading.connecting
      : stage === 'thinking'
        ? t.copilot.loading.thinking
        : stage === 'tool'
          ? format(t.copilot.loading.toolRunning, {
              tool: detail || t.copilot.loading.toolFallback,
            })
          : t.copilot.loading.streaming

  if (compact) {
    return (
      <span
        className="inline-flex items-center gap-2 text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        {stage === 'connecting' ? <ConnectingDots /> : null}
        {stage === 'streaming' ? <StreamingCursor /> : null}
        <span className="sr-only">{label}</span>
      </span>
    )
  }

  return (
    <Frame variant="ghost" spacing="xs" className="mr-8">
      <FramePanel
        className="text-sm text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        {stage === 'connecting' ? (
          <div className="flex items-center gap-2">
            <ConnectingDots />
            <span>{label}</span>
          </div>
        ) : null}
        {stage === 'thinking' ? (
          <div className="space-y-2">
            <span className="text-xs">{label}</span>
            <Skeleton className="h-3 w-full motion-reduce:animate-none" />
            <Skeleton className="h-3 w-5/6 motion-reduce:animate-none" />
            <Skeleton className="h-3 w-2/3 motion-reduce:animate-none" />
          </div>
        ) : null}
        {stage === 'tool' ? (
          <div className="space-y-2">
            <span className="text-xs">{label}</span>
            <Skeleton className="h-3 w-5/6 motion-reduce:animate-none" />
            <Skeleton className="h-3 w-2/3 motion-reduce:animate-none" />
          </div>
        ) : null}
        {stage === 'streaming' ? (
          <div className="flex items-center gap-2">
            <StreamingCursor />
            <span>{label}</span>
          </div>
        ) : null}
      </FramePanel>
    </Frame>
  )
}
