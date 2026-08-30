import { useState, type PointerEvent as ReactPointerEvent } from 'react'
import { DotsSixVerticalIcon, ChatCircleIcon, XIcon } from '@phosphor-icons/react'
import { CopilotChat } from '../../features/copilot/CopilotChat'
import { CopilotActions } from '../../features/copilot/CopilotActions'
import { CopilotAgentRuns } from '../../features/copilot/CopilotAgentRuns'
import { CopilotSettings } from '../../features/copilot/CopilotSettings'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'
import { Button } from './Button'
import { ScrollArea } from './scroll-area'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './sheet'

interface CopilotDrawerProps {
  open: boolean
  onClose: () => void
  pageContext?: string
}

export function CopilotDrawer({ open, onClose, pageContext }: CopilotDrawerProps) {
  const { t } = useI18n()
  const copilotWidth = useAppStore((s) => s.copilotWidth)
  const setCopilotWidth = useAppStore((s) => s.setCopilotWidth)
  const [settingsOpen, setSettingsOpen] = useState(false)
  // Chat and runs are the two ways to use the copilot, and they are alternatives
  // rather than companions: a transcript and a conversation both want the whole
  // drawer, and showing them at once would leave neither readable.
  const [surface, setSurface] = useState<'chat' | 'runs'>('chat')

  const startResize = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    const startX = event.clientX
    const startWidth = copilotWidth
    const onMove = (moveEvent: PointerEvent) => {
      setCopilotWidth(Math.min(560, Math.max(300, startWidth - (moveEvent.clientX - startX))))
    }
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  const resizeWithKeyboard = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    if (event.key === 'Home') return setCopilotWidth(300)
    if (event.key === 'End') return setCopilotWidth(560)
    const delta = event.shiftKey ? 40 : 16
    setCopilotWidth(Math.min(560, Math.max(300, copilotWidth + (event.key === 'ArrowLeft' ? delta : -delta))))
  }

  return (
    <Sheet open={open} onOpenChange={(nextOpen) => { if (!nextOpen) onClose() }}>
      <SheetContent
        data-tour-id="copilot-drawer"
        side="right"
        showCloseButton={false}
        className="w-full sm:max-w-none"
        style={{ width: `min(${copilotWidth}px, 100vw)` }}
      >
        <Button
          type="button"
          role="slider"
          variant="ghost"
          aria-label={t.copilot.drawer.resizeAriaLabel}
          aria-valuemin={300}
          aria-valuemax={560}
          aria-valuenow={copilotWidth}
          className="absolute inset-y-0 -left-2 z-10 flex w-4 cursor-col-resize items-center justify-center text-muted-foreground hover:text-primary"
          onPointerDown={startResize}
          onKeyDown={resizeWithKeyboard}
        >
          <DotsSixVerticalIcon className="h-4 w-4" aria-hidden="true" />
        </Button>
        <SheetHeader className="flex-row items-center justify-between border-b">
          <SheetTitle>{t.copilot.drawer.toggleLabel}</SheetTitle>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant={surface === 'runs' ? 'secondary' : 'outline'}
              size="sm"
              aria-pressed={surface === 'runs'}
              onClick={() => setSurface((value) => (value === 'runs' ? 'chat' : 'runs'))}
            >
              {t.copilot.agentRuns.toggle}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setSettingsOpen((value) => !value)}
            >
              {t.copilot.drawer.modelSettings}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={onClose}
              aria-label={t.copilot.drawer.closeAriaLabel}
            >
              <XIcon aria-hidden="true" />
            </Button>
          </div>
        </SheetHeader>
        {settingsOpen ? (
          <ScrollArea className="h-[40%] shrink-0 border-b">
            <CopilotSettings />
          </ScrollArea>
        ) : null}
        {surface === 'runs' ? (
          <ScrollArea className="min-h-0 flex-1">
            <CopilotAgentRuns />
          </ScrollArea>
        ) : (
          <>
            <div className="shrink-0">
              <CopilotActions onNavigate={onClose} />
            </div>
            <div className="min-h-0 flex-1">
              <CopilotChat pageContext={pageContext} />
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

export function CopilotToggleButton({ onClick, active }: { onClick: () => void; active?: boolean }) {
  const { t } = useI18n()
  return (
    <Button
      type="button"
      variant={active ? 'secondary' : 'outline'}
      size="sm"
      onClick={onClick}
      title={t.copilot.drawer.toggleTitle}
    >
      <ChatCircleIcon aria-hidden="true" />
      {t.copilot.drawer.toggleLabel}
    </Button>
  )
}
