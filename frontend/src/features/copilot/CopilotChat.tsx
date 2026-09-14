import { useCallback, useEffect, useRef } from 'react'
import { useCopilotReadOnly } from './commandAccess'
import { ApiState } from '../../components/ui/ApiState'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowCounterClockwiseIcon,
  LightbulbIcon,
  PaperPlaneTiltIcon,
  SpinnerGapIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import { CopilotCitations } from './CopilotCitations'
import { CopilotLoadingBubble } from './CopilotLoadingBubble'
import { useCopilotChat } from './useCopilotChat'
import { byStance, reviewersOf, successorsOf } from './bots/registry'
import { getCopilotConfig } from '../../lib/api/copilot'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { SaveToReviewButton } from '../research/SaveToReviewButton'
import { CopilotResearchImportButton } from '../research/CopilotResearchImportButton'
import { isResearchPageContext } from '../research/reviewIntent'
import { useAppStore } from '../../lib/store/appStore'
import { looksLikeCopilotResearchResult } from '../../lib/api/copilotResearch'
import { projectText } from '../../lib/i18n/projectText'
import { isQuestion } from './taskPresentation'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { ScrollArea } from '../../components/ui/scroll-area'
import { Alert, AlertDescription, AlertTitle } from '../../components/reui/alert'
import { Frame, FramePanel } from '../../components/reui/frame'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

//: The "no bot" option. Radix Select refuses an empty string as an item value,
//: and null cannot round-trip through it, so the absence of a choice needs a
//: value of its own.
const AUTO_BOT = '__auto__'

export function CopilotChat({ pageContext, initialQuestion, onTaskRequested, externalRoster = false }: { pageContext?: string; initialQuestion?: string; onTaskRequested?: (goal: string) => void; externalRoster?: boolean }) {
  const { t, format, language } = useI18n()
  const { projectId, activeProject, setProjectId, projectsLoading, projectsError, projectsQueryError, refetchProjects } = useProjectContext()
  const queryClient = useQueryClient()
  const {
    messages,
    loading,
    loadingStage,
    loadingDetail,
    error,
    send,
    resetMessages,
    lastMode,
    bots,
    bot,
    setBot,
  } = useCopilotChat(projectId, pageContext, language)
  const readOnly = useCopilotReadOnly()
  const input = useAppStore((state) => state.copilotSessions[projectId]?.input ?? '')
  const setSessionInput = useAppStore((state) => state.setCopilotSessionInput)
  const setInput = useCallback((value: string) => setSessionInput(projectId, value), [projectId, setSessionInput])
  const initialSent = useRef(false)
  useEffect(() => {
    if (!initialQuestion || initialSent.current || readOnly || projectsLoading || projectsError) return
    initialSent.current = true
    void send(initialQuestion)
  }, [initialQuestion, send, projectsLoading, projectsError, readOnly])
  const copilotDraft = useAppStore((state) => state.copilotDraft)
  const setCopilotDraft = useAppStore((state) => state.setCopilotDraft)
  const messageEndRef = useRef<HTMLDivElement | null>(null)
  const copilotConfig = useQuery({
    queryKey: ['copilot-config', projectId],
    queryFn: () => getCopilotConfig(projectId),
    enabled: Boolean(projectId),
    staleTime: 60_000,
  })
  const visibleMessages = messages.filter((message) => message.role !== 'system')
  const lastMessage = visibleMessages[visibleMessages.length - 1]
  const showLoadingCard =
    loading &&
    loadingStage !== 'idle' &&
    (!lastMessage || lastMessage.role !== 'assistant' || !lastMessage.content)
  const activeLoadingStage = loadingStage !== 'idle' ? loadingStage : 'thinking'
  const onResearchPage = isResearchPageContext(pageContext)

  const rawProjectTopic = activeProject
    ? projectText(activeProject, 'summary', language).trim() ||
      projectText(activeProject, 'name', language)
    : t.copilot.chat.defaultProjectTopic
  const projectTopic = rawProjectTopic.replace(/[.!?]+$/, '')
  const typeLabel =
    activeProject?.project_type?.replace(/_/g, ' ') || t.copilot.chat.defaultProjectType
  const starters = [
    format(t.copilot.chat.starterPlanRoute, { typeLabel, projectTopic }),
    t.copilot.chat.starterExplainCandidate,
    pageContext?.includes('results')
      ? t.copilot.chat.starterInterpretResults
      : t.copilot.chat.starterNextStep,
  ]
  const degradedMode =
    copilotConfig.data?.api_key_configured === false ||
    lastMode === 'rule_based_demo'

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed || loading || readOnly) return
    setInput('')
    if (onTaskRequested && !isQuestion(trimmed) && /帮我|请.*(?:调研|生成|起草)|research|prepare|draft|plan|检索|调研/i.test(trimmed)) { onTaskRequested(trimmed); return }
    await send(trimmed)
  }

  useEffect(() => {
    if (!copilotDraft || projectsLoading || projectsError) return
    const timer = window.setTimeout(() => {
      setInput(copilotDraft)
      setCopilotDraft('')
    }, 0)
    return () => window.clearTimeout(timer)
  }, [copilotDraft, setCopilotDraft, setInput, projectsLoading, projectsError])

  const sendStarter = async (starter: string) => {
    if (loading || readOnly) return
    setInput('')
    await send(starter)
  }

  useEffect(() => {
    messageEndRef.current?.scrollIntoView?.({ block: 'end' })
  }, [visibleMessages, loadingStage])

  // Resolved against the served roster rather than stored: a selection that
  // outlived a deploy which retired its operator shows nothing instead of a
  // charter the server no longer honours.
  const activeBotSpec = bot ? (bots.find((entry) => entry.id === bot) ?? null) : null
  const reviewers = activeBotSpec ? reviewersOf(activeBotSpec, bots) : []
  const successors = activeBotSpec ? successorsOf(activeBotSpec, bots) : []
  const byId = new Map(bots.map((entry) => [entry.id, entry]))
  const directs = (activeBotSpec?.directs ?? []).flatMap((id) => {
    const target = byId.get(id)
    return target ? [target] : []
  })

  if (projectsLoading || projectsError) return <ApiState isLoading={projectsLoading} isError={projectsError} error={projectsQueryError} onRetry={() => void refetchProjects()}>{null}</ApiState>

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {readOnly ? <p role="status" className="p-4 text-sm text-text-secondary">{language === 'zh' ? '只读模式：可以查看对话，不能发送新请求。' : 'Read-only mode: you can inspect conversations but cannot send requests.'}</p> : null}
      <div className="flex items-center justify-between gap-2 border-b px-4 py-2">
        {/* Which project this conversation is bound to. Kept, and kept first:
            the drawer stays open while the reader navigates, and every answer
            here is project-scoped - a chat that does not say whose data it is
            reading is the one thing in this header worth the width. */}
        <span className="min-w-0 shrink truncate text-xs text-muted-foreground">
          {projectId
            ? format(t.copilot.chat.projectContext, { projectId })
            : t.copilot.chat.selectProjectHint}
        </span>
        {bots.length > 0 && !externalRoster ? (
          <Select
            value={bot ?? AUTO_BOT}
            onValueChange={(next) => setBot(next === AUTO_BOT ? null : next)}
          >
            <SelectTrigger className="h-7 w-36 shrink-0 text-xs" aria-label={t.copilot.chat.botLabel}>
              <SelectValue placeholder={t.copilot.chat.botAuto} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={AUTO_BOT}>{t.copilot.chat.botAuto}</SelectItem>
              {/* Grouped by stance, not by phase. A director is not the step
                  before research and a reviewer is not the step after
                  archiving; a single ordered list says they are, which is the
                  reading this roster exists to correct.

                  One line per option, not two. The summary belongs to the
                  selected operator's row below: `SelectItem` renders its
                  children inside `ItemText`, whose own layout classes stack
                  against a two-line child, and an option whose accessible name
                  is "Planner Choose the route and draft the compute" is worse
                  to hear than to read. */}
              {byStance(bots).map((group) => (
                <SelectGroup key={group.stance}>
                  <SelectLabel>{t.copilot.chat.botStances[group.stance]}</SelectLabel>
                  {group.bots.map((entry) => (
                    <SelectItem key={entry.id} value={entry.id} title={entry.summary}>
                      {language === 'zh' ? entry.title_zh : entry.title}
                    </SelectItem>
                  ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>
        ) : null}
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={t.copilot.chat.resetAriaLabel}
          title={t.copilot.chat.resetTitle}
          disabled={readOnly || loading}
          onClick={resetMessages}
        >
          <ArrowCounterClockwiseIcon aria-hidden="true" />
        </Button>
      </div>
      {/* What the selected operator refuses, who checks it, and where it hands
          on. All of it was in the roster response already and none of it reached
          the screen, which made selecting one a gesture rather than a decision.
          Only when a bot is chosen: the undifferentiated case has no charter to
          show and the row would be permanent chrome. */}
      {activeBotSpec && !externalRoster ? (
        <div className="shrink-0 border-b bg-muted/40 px-4 py-2">
          <p className="text-xs font-medium text-foreground">{activeBotSpec.summary}</p>
          <p className="mt-1 text-xs text-muted-foreground">{activeBotSpec.charter}</p>
          {reviewers.length > 0 ? (
            <p className="mt-1 text-[11px] text-muted-foreground">
              {t.copilot.chat.reviewedBy}{' '}
              {reviewers.map((entry) => (language === 'zh' ? entry.title_zh : entry.title)).join('、')}
            </p>
          ) : null}
          {directs.length > 0 ? (
            // A director's declared reach. Served on every roster response and
            // displayed nowhere until now, which left the one operator whose
            // whole job is choosing another unable to show which ones.
            <p className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
              {t.copilot.chat.directs}
              {directs.map((entry) => (
                <Button
                  key={entry.id}
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-[11px]"
                  onClick={() => setBot(entry.id)}
                >
                  {language === 'zh' ? entry.title_zh : entry.title}
                </Button>
              ))}
            </p>
          ) : null}
          {successors.length > 0 ? (
            <p className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
              {t.copilot.chat.handsTo}
              {successors.map((entry) => (
                <Button
                  key={entry.id}
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-[11px]"
                  onClick={() => setBot(entry.id)}
                >
                  {language === 'zh' ? entry.title_zh : entry.title}
                </Button>
              ))}
            </p>
          ) : null}
        </div>
      ) : null}
      <ScrollArea className="min-h-0 flex-1" aria-label={t.copilot.chat.conversationLabel}>
        <div className="space-y-3 p-4 pr-6">
          {error ? (
            <Alert variant="destructive">
              <WarningIcon aria-hidden="true" />
              <AlertTitle>{t.copilot.chat.failedTitle}</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          {degradedMode ? (
            <Alert variant="warning" role="status">
              <WarningIcon aria-hidden="true" />
              <AlertDescription>{t.copilot.chat.degradedModeBanner}</AlertDescription>
            </Alert>
          ) : null}
          {visibleMessages.length === 0 ? (
            <Frame spacing="sm">
              <FramePanel>
                <div className="flex items-start gap-3">
                  <LightbulbIcon
                    className="mt-0.5 size-4 shrink-0 text-primary"
                    aria-hidden="true"
                  />
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">
                      {t.copilot.chat.emptyTitle}
                    </h3>
                    <ul className="mt-2 grid gap-1 text-xs text-muted-foreground">
                      <li>{t.copilot.chat.emptyBullet1}</li>
                      <li>{t.copilot.chat.emptyBullet2}</li>
                      <li>{t.copilot.chat.emptyBullet3}</li>
                    </ul>
                  </div>
                </div>
                <div className="mt-4 grid gap-2">
                  {starters.map((starter) => (
                    <Button
                      key={starter}
                      type="button"
                      variant="outline"
                      className="h-auto justify-start whitespace-normal text-left"
                      disabled={readOnly || loading}
                      onClick={() => void sendStarter(starter)}
                    >
                      {starter}
                    </Button>
                  ))}
                </div>
              </FramePanel>
            </Frame>
          ) : null}
          {visibleMessages.map((message, index) => {
            const userMessage =
              message.role === 'assistant'
                ? [...visibleMessages.slice(0, index)]
                    .reverse()
                    .find((item) => item.role === 'user')
                : undefined
            const showSaveButton =
              !readOnly && message.role === 'assistant' &&
              Boolean(message.content) &&
              !loading &&
              projectId &&
              (userMessage?.meta?.reviewTrack ||
                userMessage?.meta?.reviewIntent ||
                onResearchPage)
            const showResearchImport =
              !readOnly && message.role === 'assistant' &&
              !loading &&
              Boolean(activeProject?.organization_id) &&
              looksLikeCopilotResearchResult(message.content)

            return (
              <Frame
                key={`${message.role}-${index}`}
                variant={message.role === 'user' ? 'inverse' : 'default'}
                spacing="xs"
                className={message.role === 'user' ? 'ml-8' : 'mr-8'}
              >
                <FramePanel className="whitespace-pre-wrap break-words text-sm text-muted-foreground">
                  {message.content ||
                    (loading && message.role === 'assistant' ? (
                      <CopilotLoadingBubble
                        stage={activeLoadingStage}
                        detail={loadingDetail}
                        compact
                      />
                    ) : (
                      ''
                    ))}
                  {message.role === 'assistant' && message.meta?.citations?.length ? (
                    <CopilotCitations citations={message.meta.citations} projectId={projectId} />
                  ) : null}
                  {showSaveButton ? (
                    <SaveToReviewButton
                      projectId={projectId}
                      content={message.content}
                      reviewTrack={userMessage?.meta?.reviewTrack}
                      reviewIntent={userMessage?.meta?.reviewIntent}
                      userPrompt={userMessage?.content}
                      onResearchPage={onResearchPage}
                      citations={message.meta?.citations}
                    />
                  ) : null}
                  {showResearchImport ? (
                    <CopilotResearchImportButton
                      organizationId={activeProject!.organization_id}
                      content={message.content}
                      onImported={async (imported) => {
                        await queryClient.invalidateQueries({ queryKey: ['projects'] })
                        await queryClient.invalidateQueries({ queryKey: ['project-library'] })
                        setProjectId(imported.project_id)
                      }}
                    />
                  ) : null}
                </FramePanel>
              </Frame>
            )
          })}
          {showLoadingCard ? (
            <CopilotLoadingBubble stage={activeLoadingStage} detail={loadingDetail} />
          ) : null}
          <div ref={messageEndRef} />
        </div>
      </ScrollArea>
      <div className="flex items-center gap-2 border-t p-3">
        <label htmlFor="copilot-input" className="sr-only">
          {t.copilot.chat.inputLabel}
        </label>
        <Input
          id="copilot-input"
          aria-label={t.copilot.chat.inputLabel}
          placeholder={t.copilot.chat.inputPlaceholder}
          className="flex-1"
          value={input}
          disabled={readOnly || loading}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter' || event.nativeEvent.isComposing) return
            event.preventDefault()
            void handleSend()
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label={t.copilot.chat.sendAriaLabel}
          disabled={readOnly || loading || !input.trim()}
          onClick={() => void handleSend()}
        >
          {loading ? (
            <SpinnerGapIcon
              className="animate-spin motion-reduce:animate-none"
              aria-hidden="true"
            />
          ) : (
            <PaperPlaneTiltIcon aria-hidden="true" />
          )}
        </Button>
      </div>
    </div>
  )
}
