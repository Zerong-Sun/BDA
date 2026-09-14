import { useState, type PointerEvent as ReactPointerEvent } from 'react'
import { DotsSixVerticalIcon, ChatCircleIcon, XIcon } from '@phosphor-icons/react'
import { CopilotChat } from '../../features/copilot/CopilotChat'
import { CopilotActions } from '../../features/copilot/CopilotActions'
import { CopilotChain } from '../../features/copilot/CopilotChain'
import { CopilotMcpSessions } from '../../features/copilot/CopilotMcpSessions'
import { CopilotWorkspace } from '../../features/copilot/CopilotWorkspace'
import { CopilotSettings } from '../../features/copilot/CopilotSettings'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { managesProject, useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { currentRole } from '../../features/research/jsonHelpers'
import { resolveBot, useCopilotBots } from '../../features/copilot/bots/registry'
import { useAppStore } from '../../lib/store/appStore'
import { Button } from './Button'
import { ScrollArea } from './scroll-area'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './sheet'
import { Tabs, TabsList, TabsTrigger } from './Tabs'

interface CopilotDrawerProps {
  open: boolean
  onClose: () => void
  pageContext?: string
}

export function CopilotDrawer({ open, onClose, pageContext }: CopilotDrawerProps) {
  const { t, language } = useI18n()
  const copilotWidth = useAppStore((s) => s.copilotWidth)
  const setCopilotWidth = useAppStore((s) => s.setCopilotWidth)
  // Written into the per-project session rather than passed down, because that is
  // where `useCopilotChat` reads the selected operator from - handing it through
  // props would be a second source for one selection.
  const { projectId } = useProjectContext()
  const setCopilotSessionBot = useAppStore((s) => s.setCopilotSessionBot)
  const [settingsOpen, setSettingsOpen] = useState(false)
  // Model configuration is a project manager's decision, as on the Research team page.
  const access = useProjectAccess(projectId)
  const canConfigure = managesProject(access.data) || currentRole() === 'admin'
  const bots = useCopilotBots()
  // Chat, the chain record, runs and MCP grants are alternatives rather than
  // companions: a transcript and a conversation both want the whole drawer, and
  // showing them at once would leave neither readable. MCP sits here rather than
  // in settings because a grant is scoped to a run and a project, which is what
  // this drawer is already about - settings is where the model provider lives.
  //
  // A tab set rather than four toggle buttons. They were already mutually
  // exclusive and already announced `aria-pressed`, which is a tab group wearing
  // buttons: arrow keys did not move between them, and four of them beside a
  // title and a close button wrapped in a 300px drawer. `Tabs` is already in the
  // repo and says the right thing to a screen reader without being told.
  //
  // Named as on the Research team page. The separate run list is gone: every task
  // is already listed, under its owner, in Tasks & deliverables.
  const [surface, setSurface] = useState<'tasks' | 'chat' | 'chain' | 'mcp'>('tasks')

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
        <SheetHeader className="flex-row items-center justify-between gap-2 border-b">
          <SheetTitle className="truncate text-sm">{t.copilot.drawer.toggleLabel}</SheetTitle>
          <div className="flex shrink-0 items-center gap-1">
            {canConfigure ? (
              <Button
                type="button"
                variant={settingsOpen ? 'secondary' : 'ghost'}
                size="sm"
                aria-pressed={settingsOpen}
                onClick={() => setSettingsOpen((value) => !value)}
              >
                {t.copilot.drawer.modelSettings}
              </Button>
            ) : null}
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
        {/* On its own row: four labels plus the header's own controls do not fit
            across a 300px drawer, and wrapping them put the close button under
            the title. */}
        <Tabs
          value={surface}
          onValueChange={(value) => setSurface(value as typeof surface)}
          className="shrink-0 border-b px-2 pb-1"
        >
          <TabsList variant="line" className="w-full justify-start gap-0.5 overflow-x-auto">
            <TabsTrigger value="tasks">{language === 'zh' ? '任务与交付' : 'Tasks & deliverables'}</TabsTrigger>
            <TabsTrigger value="chat">{language === 'zh' ? '对话' : 'Conversation'}</TabsTrigger>
            <TabsTrigger value="chain">{language === 'zh' ? 'Bot 交接' : 'Bot handoffs'}</TabsTrigger>
            <TabsTrigger value="mcp">{language === 'zh' ? '外部接入' : 'External access'}</TabsTrigger>
          </TabsList>
        </Tabs>
        {settingsOpen && canConfigure ? (
          <ScrollArea className="h-[40%] shrink-0 border-b">
            <CopilotSettings />
          </ScrollArea>
        ) : null}
        {surface === 'tasks' ? (
          <CopilotWorkspace pageContext={pageContext} />
        ) : surface === 'mcp' ? (
          <ScrollArea className="min-h-0 flex-1">
            <CopilotMcpSessions />
          </ScrollArea>
        ) : surface === 'chain' ? (
          <ScrollArea className="min-h-0 flex-1">
            {/* Naming the successor moves the reader to it. Reading what was
                handed over and then hunting for the recipient in the chat's own
                dropdown is the handoff protocol working on paper only. */}
            <CopilotChain
              onSelectOperator={(botId) => {
                // A handover recorded under a retired id names the operator that absorbed it.
                if (projectId) setCopilotSessionBot(projectId, resolveBot(botId, bots.data ?? [])?.id ?? botId)
                setSurface('chat')
              }}
            />
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
