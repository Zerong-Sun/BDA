import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowCounterClockwiseIcon,
  LightbulbIcon,
  PaperPlaneTiltIcon,
  SpinnerGapIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import { Link } from 'react-router'
import { CopilotLoadingBubble } from './CopilotLoadingBubble'
import { useCopilotChat } from './useCopilotChat'
import { getCopilotConfig } from '../../lib/api/copilot'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { SaveToReviewButton } from '../research/SaveToReviewButton'
import { CopilotResearchImportButton } from '../research/CopilotResearchImportButton'
import { isResearchPageContext } from '../research/reviewIntent'
import { useAppStore } from '../../lib/store/appStore'
import { looksLikeCopilotResearchResult } from '../../lib/api/copilotResearch'
import { projectText } from '../../lib/i18n/projectText'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { ScrollArea } from '../../components/ui/scroll-area'
import { Alert, AlertDescription, AlertTitle } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Frame, FramePanel } from '../../components/reui/frame'

export function CopilotChat({ pageContext }: { pageContext?: string }) {
  const { t, format, language } = useI18n()
  const { projectId, activeProject, setProjectId } = useProjectContext()
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
  } = useCopilotChat(projectId, pageContext, language)
  const [input, setInput] = useState('')
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
    lastMode === 'rule_based_demo' ||
    (typeof window !== 'undefined' &&
      sessionStorage.getItem('bda_copilot_last_mode') === 'rule_based_demo')

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed) return
    setInput('')
    await send(trimmed)
  }

  useEffect(() => {
    if (!copilotDraft) return
    const timer = window.setTimeout(() => {
      setInput(copilotDraft)
      setCopilotDraft('')
    }, 0)
    return () => window.clearTimeout(timer)
  }, [copilotDraft, setCopilotDraft])

  const sendStarter = async (starter: string) => {
    setInput('')
    await send(starter)
  }

  useEffect(() => {
    messageEndRef.current?.scrollIntoView?.({ block: 'end' })
  }, [visibleMessages, loadingStage])

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <span className="text-xs text-muted-foreground">
          {projectId
            ? format(t.copilot.chat.projectContext, { projectId })
            : t.copilot.chat.selectProjectHint}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={t.copilot.chat.resetAriaLabel}
          title={t.copilot.chat.resetTitle}
          disabled={loading}
          onClick={resetMessages}
        >
          <ArrowCounterClockwiseIcon aria-hidden="true" />
        </Button>
      </div>
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
                      disabled={loading}
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
              message.role === 'assistant' &&
              Boolean(message.content) &&
              !loading &&
              projectId &&
              (userMessage?.meta?.reviewTrack ||
                userMessage?.meta?.reviewIntent ||
                onResearchPage)
            const showResearchImport =
              message.role === 'assistant' &&
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
                    <div className="mt-3 flex flex-wrap gap-1.5 border-t pt-2">
                      {message.meta.citations.map((citation, citationIndex) => {
                        const url = typeof citation.url === 'string' ? citation.url : ''
                        const label = String(
                          citation.label ||
                            citation.entity_id ||
                            citation.workspace_type ||
                            format(t.copilot.chat.citationSourceFallback, {
                              index: citationIndex + 1,
                            }),
                        )
                        const evidence = [citation.evidence_grade, citation.review_status]
                          .filter(Boolean)
                          .join(' · ')
                        const internal = citation.source_type === 'research_workspace'
                        const origin = internal
                          ? t.copilot.chat.citationProject
                          : t.copilot.chat.citationExternal
                        const accessibleLabel = [label, origin, evidence]
                          .filter(Boolean)
                          .join(' ')
                        const kind = String(citation.workspace_type || '')
                        const tab =
                          kind === 'reference'
                            ? 'references'
                            : kind === 'structure'
                              ? 'structures'
                              : ['dataset', 'research_target'].includes(kind)
                                ? 'data'
                                : kind === 'method'
                                  ? 'methods'
                                  : 'evidence'
                        const badge = (
                          <Badge
                            variant={internal ? 'info-light' : 'outline'}
                            size="xs"
                            className="h-auto whitespace-normal py-1"
                          >
                            <span>{label}</span>
                            <span className="text-[9px] uppercase">
                              {origin}
                              {evidence ? ` · ${String(evidence)}` : ''}
                            </span>
                          </Badge>
                        )
                        const key = `${String(citation.entity_id)}-${citationIndex}`
                        return url ? (
                          <a
                            key={key}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={accessibleLabel}
                            className="hover:underline"
                          >
                            {badge}
                          </a>
                        ) : internal && projectId ? (
                          <Link
                            key={key}
                            to={`/research?tab=${tab}&project=${encodeURIComponent(projectId)}`}
                            aria-label={accessibleLabel}
                            className="hover:underline"
                          >
                            {badge}
                          </Link>
                        ) : (
                          <span key={key}>{badge}</span>
                        )
                      })}
                    </div>
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
          disabled={loading}
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
          disabled={loading || !input.trim()}
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
