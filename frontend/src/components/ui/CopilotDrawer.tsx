import { lazy, Suspense, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { useLocation } from 'react-router'
import { DotsSixVerticalIcon, DotsThreeIcon, ChatCircleIcon, XIcon } from '@phosphor-icons/react'
import { CopilotChat } from '../../features/copilot/CopilotChat'
import { CopilotActions } from '../../features/copilot/CopilotActions'
import { CopilotChain } from '../../features/copilot/CopilotChain'
const CopilotMcpSessions = lazy(() => import('../../features/copilot/CopilotMcpSessions').then((module) => ({ default: module.CopilotMcpSessions })))
import { CopilotWorkspace } from '../../features/copilot/CopilotWorkspace'
import { CopilotReview } from '../../features/copilot/CopilotReview'
const CopilotSettings = lazy(() => import('../../features/copilot/CopilotSettings').then((module) => ({ default: module.CopilotSettings })))
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { useCopilotReadOnly } from '../../features/copilot/commandAccess'
import { currentRole } from '../../features/research/jsonHelpers'
import { resolveBot, useCopilotBots } from '../../features/copilot/bots/registry'
import { useAppStore } from '../../lib/store/appStore'
import { Button } from './Button'
import { ScrollArea } from './scroll-area'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './sheet'
import { Tabs, TabsList, TabsTrigger, TabsContent } from './Tabs'
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuTrigger } from './dropdown-menu'

interface CopilotDrawerProps {
  open: boolean
  onClose: () => void
  pageContext?: string
}

export function CopilotDrawer({ open, onClose, pageContext }: CopilotDrawerProps) {
  const { t, language } = useI18n()
  const location = useLocation()
  const tourActive = useAppStore((state) => state.tourState.status === 'active')
  const route = `${location.pathname}${location.search}`
  const previousRoute = useRef(route)
  useEffect(() => {
    // Follow real navigation, including links from tool evidence and deliveries.
    // The destination must not stay obscured by the modal that initiated it.
    // An active tour coordinates navigation and the drawer together.
    if (previousRoute.current !== route && open && !tourActive) onClose()
    previousRoute.current = route
  }, [route, open, onClose, tourActive])
  const copilotWidth = useAppStore((s) => s.copilotWidth)
  const setCopilotWidth = useAppStore((s) => s.setCopilotWidth)
  // Written into the per-project session rather than passed down, because that is
  // where `useCopilotChat` reads the selected operator from - handing it through
  // props would be a second source for one selection.
  const { projectId, activeProject } = useProjectContext()
  const setCopilotSessionBot = useAppStore((s) => s.setCopilotSessionBot)
  const [settingsOpen, setSettingsOpen] = useState(false)
  // Match the config API's project-write permission, as in application settings.
  const access = useProjectAccess(projectId)
  const readOnly = useCopilotReadOnly()
  const canConfigure = !readOnly && (access.data?.permissions.write === true || currentRole() === 'admin')
  const bots = useCopilotBots()
  // Primary intents stay visible. Infrequent handoffs and access grants belong
  // in the overflow menu; neither is a second task creation path.
  const [surface, setSurface] = useState<'tasks' | 'review' | 'chat' | 'chain' | 'mcp'>('tasks')

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
        className="copilot-console w-full sm:max-w-none"
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
          <div className="min-w-0">
            <SheetTitle className="truncate text-sm">{t.copilot.drawer.toggleLabel}</SheetTitle>
            <p className="truncate text-xs text-text-secondary" title={activeProject?.name}>{activeProject?.name ?? (language === 'zh' ? '未选择项目' : 'No project selected')}</p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button type="button" variant="ghost" size="icon-sm" />} aria-label={language === 'zh' ? '更多助手工具' : 'More assistant tools'}><DotsThreeIcon aria-hidden="true" /></DropdownMenuTrigger>
              <DropdownMenuContent align="end"><DropdownMenuGroup>
                <DropdownMenuItem onClick={() => { setSettingsOpen(false); setSurface('chain') }}>{language === 'zh' ? 'Bot 交接' : 'Bot handoffs'}</DropdownMenuItem>
                <DropdownMenuItem onClick={() => { setSettingsOpen(false); setSurface('mcp') }}>{language === 'zh' ? '外部接入' : 'External access'}</DropdownMenuItem>
              </DropdownMenuGroup></DropdownMenuContent>
            </DropdownMenu>
            {canConfigure ? (
              <Button
                type="button"
                variant={settingsOpen ? 'secondary' : 'ghost'}
                size="sm"
                aria-pressed={settingsOpen}
                onClick={() => setSettingsOpen((value) => !value)}
              >
                {settingsOpen ? (language === 'zh' ? '返回助手' : 'Back to assistant') : t.copilot.drawer.modelSettings}
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
        {settingsOpen && canConfigure ? (
          <ScrollArea className="min-h-0 flex-1">
            <Suspense fallback={null}><CopilotSettings /></Suspense>
          </ScrollArea>
        ) : null}
        <Tabs
          hidden={settingsOpen && canConfigure}
          value={surface}
          onValueChange={(value) => setSurface(value as typeof surface)}
          className={settingsOpen && canConfigure ? 'hidden' : 'min-h-0 flex-1 gap-0'}
        >
          <TabsList variant="line" className="grid h-auto! w-full shrink-0 grid-cols-3 border-b px-2">
            <TabsTrigger className="min-h-11 min-w-0 whitespace-normal leading-tight" value="tasks">{language === 'zh' ? '发起任务' : 'Start a task'}</TabsTrigger>
            <TabsTrigger className="min-h-11 min-w-0 whitespace-normal leading-tight" value="review">{language === 'zh' ? '决策与参数' : 'Decisions & parameters'}</TabsTrigger>
            <TabsTrigger className="min-h-11 min-w-0 whitespace-normal leading-tight" value="chat">{language === 'zh' ? '对话' : 'Conversation'}</TabsTrigger>
          </TabsList>
          <TabsContent value="tasks" keepMounted className="min-h-0 overflow-y-auto">
            <CopilotWorkspace pageContext={pageContext} rememberDraft onConfigureModel={canConfigure ? () => setSettingsOpen(true) : undefined} />
          </TabsContent>
          <TabsContent value="review" className="min-h-0 overflow-y-auto">
            <CopilotReview />
          </TabsContent>
          <TabsContent value="chat" className="min-h-0 overflow-hidden">
            <div className="flex h-full min-h-0 flex-col">
              <CopilotActions onNavigate={onClose} />
              <div className="min-h-0 flex-1"><CopilotChat pageContext={pageContext} /></div>
            </div>
          </TabsContent>
        {surface === 'mcp' ? (
          <ScrollArea className="min-h-0 flex-1">
            <h3 className="px-4 pt-3 font-semibold">{language === 'zh' ? '外部接入' : 'External access'}</h3>
            <Suspense fallback={null}><CopilotMcpSessions /></Suspense>
          </ScrollArea>
        ) : surface === 'chain' ? (
          <ScrollArea className="min-h-0 flex-1">
            <h3 className="px-4 pt-3 font-semibold">{language === 'zh' ? 'Bot 交接' : 'Bot handoffs'}</h3>
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
        ) : null}
        </Tabs>
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
