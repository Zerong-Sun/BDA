import { useEffect, useRef, useState } from 'react'
import { PaperPlaneTiltIcon, SpinnerGapIcon, XIcon } from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { DecisionRequestResponse, RoomEvent } from '../../lib/api/generated'
import { ApiError } from '../../lib/api/client'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'
import { ApiState } from '../../components/ui/ApiState'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { ScrollArea } from '../../components/ui/scroll-area'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { BotAvatar } from './BotAvatar'
import { CopilotCitations } from './CopilotCitations'
import { CopilotLoadingBubble } from './CopilotLoadingBubble'
import { HandoffCard } from './CopilotChain'
import { ownedService, parseMention } from './mentions'
import { answerDecisionRequest, decisionRequestsQueryKey, withdrawDecisionRequest } from './decisionRequests'
import { useCopilotReadOnly } from './commandAccess'
import { resolveBot, useCopilotBots, type CopilotBot } from './bots/registry'
import { childTasksByParent, copilotRoomQueryKey, inReadingOrder, topLevelEntries, useCopilotRoom } from './roomFeed'
import { roomTaskLabel } from './taskPresentation'
import { useCopilotChat } from './useCopilotChat'

/**
 * The project's research room.
 *
 * Everything the team does was already recorded; until now it was recorded in
 * three places a reader had to interleave by eye. This renders one order.
 *
 * Two properties are deliberate and worth stating where they can be checked:
 *
 * **The server is the transcript.** Entries come from `/copilot/…/room`, not
 * from the chat store, so a reload no longer empties the conversation. The
 * store is used for exactly one thing - the turn currently in flight, which has
 * no row yet - and that bubble is replaced by the recorded one as soon as the
 * turn ends.
 *
 * **No operator speaks unless it did.** A handover is rendered as the row it
 * is, a delegated task nests under the task that opened it, and there is no
 * path here that could produce a line of dialogue nobody wrote.
 */
export function Room({
  pageContext,
  onOpenRun,
  onOpenBot,
  onAssign,
}: {
  pageContext?: string
  onOpenRun?: (runId: string) => void
  onOpenBot?: (botId: string) => void
  /**
   * Hand this work to an operator as a guided task. The room prepares it and
   * nothing more: the plan, the writes and the budget are still reviewed in the
   * composer, because starting a run spends money and a room message is not a
   * place to approve that.
   */
  onAssign?: (goal: string, botId: string, service: string) => void
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const { projectId } = useProjectContext()
  const queryClient = useQueryClient()
  const readOnly = useCopilotReadOnly()
  const bots = useCopilotBots()
  const roster = bots.data ?? []
  const feed = useCopilotRoom(projectId || null)
  const { send, loading, loadingStage, loadingDetail, error, messages } = useCopilotChat(
    projectId,
    pageContext,
    language,
  )
  const input = useAppStore((state) => state.copilotSessions[projectId]?.input ?? '')
  const setSessionInput = useAppStore((state) => state.setCopilotSessionInput)
  // What the next message carries. Pages that ask the team about something -
  // a structure, a finding - select it; until now that selection travelled
  // with the message invisibly, so a person could not tell what the team
  // would be looking at, or take something back out.
  const attachedIds = useAppStore((state) => state.copilotSessions[projectId]?.selectedEntityIds) ?? NO_IDS
  const attachedLabels = useAppStore((state) => state.copilotSessions[projectId]?.selectedEntityLabels) ?? NO_LABELS
  const setAttached = useAppStore((state) => state.setCopilotSelectedEntityIds)
  const endRef = useRef<HTMLDivElement | null>(null)

  // A finished turn has rows the feed has not read yet. Keyed on the fall of
  // `loading` rather than refetched on a timer: a conversation nobody is
  // talking in should cost nothing.
  const wasLoading = useRef(false)
  useEffect(() => {
    if (wasLoading.current && !loading && projectId) {
      void queryClient.invalidateQueries({ queryKey: copilotRoomQueryKey(projectId) })
    }
    wasLoading.current = loading
  }, [loading, projectId, queryClient])

  const entries = inReadingOrder(feed.data ?? [])
  const children = childTasksByParent(entries)
  const visible = topLevelEntries(entries)
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' })
  }, [visible.length, loading])

  // The turn in flight. Its user message is already a row, but the room only
  // refetches when the turn ends, so both halves are echoed until then.
  const pending = loading ? messages.slice(-2) : []

  // Who this message is addressed to, recomputed as it is typed so the room can
  // show the addressee before it is sent rather than after.
  const mention = parseMention(input, roster)
  const addressee = mention?.bot
  const unknownHandle = mention && !mention.bot ? mention.handle : null
  const assignable = addressee ? ownedService(addressee) : undefined

  const handleSend = async () => {
    const trimmed = input.trim()
    // A handle naming nobody is refused rather than quietly auto-matched: the
    // person believes they addressed someone, and sending it elsewhere without
    // saying so is the failure this check exists for.
    if (!trimmed || loading || readOnly || unknownHandle) return
    setSessionInput(projectId, '')
    await send(trimmed, addressee ? { bot: addressee.id } : undefined)
  }

  return (
    <div className="room" data-tour-id="research-room">
      <ApiState
        isLoading={feed.isLoading}
        isError={feed.isError}
        error={feed.error}
        onRetry={() => void feed.refetch()}
      >
        <ScrollArea className="room-scroll">
          <div className="room-feed">
            {visible.length === 0 && !loading ? (
              <p className="room-empty" role="status">
                {zh
                  ? '这里会记录团队的每一次发言、交接与任务。说点什么，或者 @ 一位成员。'
                  : 'Every message, handover and task in this project appears here. Say something, or @ a member.'}
              </p>
            ) : null}
            {visible.map((entry) => (
              <RoomEntry
                key={`${entry.kind}-${entry.id}`}
                entry={entry}
                roster={roster}
                projectId={projectId}
                zh={zh}
                childTasks={entry.task ? children.get(entry.task.id) ?? [] : []}
                onOpenRun={onOpenRun}
                onOpenBot={onOpenBot}
              />
            ))}
            {pending.map((message, index) => (
              <article className="room-entry" key={`pending-${index}`}>
                <div className="room-entry-body">
                  <p className="room-speaker">
                    {message.role === 'user' ? (zh ? '你' : 'You') : zh ? '正在回复' : 'Replying'}
                  </p>
                  <div className="room-text">
                    {message.content || (
                      <CopilotLoadingBubble
                        stage={loadingStage === 'idle' ? 'thinking' : loadingStage}
                        detail={loadingDetail}
                        compact
                      />
                    )}
                  </div>
                </div>
              </article>
            ))}
            <div ref={endRef} />
          </div>
        </ScrollArea>
      </ApiState>
      {error ? (
        <Alert variant="destructive" className="mt-2">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {addressee || unknownHandle ? (
        <p className="room-addressee" role="status">
          {addressee ? (
            <>
              <span>{zh ? '发给' : 'To'} <strong>{zh ? addressee.title_zh : addressee.title}</strong></span>
              {assignable && onAssign && !readOnly ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onAssign((mention?.body || input).trim(), addressee.id, assignable)}
                  disabled={!(mention?.body || input).trim()}
                >
                  {zh ? '交给 TA 办' : 'Hand it to them'}
                </Button>
              ) : null}
            </>
          ) : (
            <span>
              {zh
                ? `团队里没有叫「${unknownHandle}」的成员，改一下再发。`
                : `No member is called “${unknownHandle}”. Change the name to send.`}
            </span>
          )}
        </p>
      ) : null}
      {attachedIds.length ? (
        <div
          className="room-attachments"
          role="group"
          aria-label={zh ? '随下一条消息附带' : 'Attached to your next message'}
        >
          <span className="room-attachments-label">{zh ? '附带' : 'Attached'}</span>
          {attachedIds.map((id) => {
            // An id with no label is shown as the id: hiding it would make the
            // message carry something the person cannot see.
            const label = attachedLabels[id] ?? id
            return (
              <span key={id} className="room-attachment" title={id}>
                <span className="room-attachment-name">{label}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  className="room-attachment-remove"
                  aria-label={`${zh ? '移除' : 'Remove'} ${label}`}
                  disabled={loading}
                  onClick={() => setAttached(attachedIds.filter((item) => item !== id), projectId, attachedLabels)}
                >
                  <XIcon aria-hidden="true" />
                </Button>
              </span>
            )
          })}
        </div>
      ) : null}
      <div className="room-composer">
        <label htmlFor="room-input" className="sr-only">
          {zh ? '在研究室里发言' : 'Say something in the room'}
        </label>
        <Input
          id="room-input"
          aria-label={zh ? '在研究室里发言' : 'Say something in the room'}
          placeholder={zh ? '说明你想完成什么' : 'Describe what you want to get done'}
          value={input}
          disabled={readOnly || loading}
          onChange={(event) => setSessionInput(projectId, event.target.value)}
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
          aria-label={zh ? '发送' : 'Send'}
          disabled={readOnly || loading || !input.trim() || Boolean(unknownHandle)}
          onClick={() => void handleSend()}
        >
          {loading ? (
            <SpinnerGapIcon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
          ) : (
            <PaperPlaneTiltIcon aria-hidden="true" />
          )}
        </Button>
      </div>
      {readOnly ? (
        <p className="room-readonly" role="status">
          {zh
            ? '只读模式：可以查看研究室，发言需要研究员权限。'
            : 'Read-only mode: you can read the room; speaking needs researcher access.'}
        </p>
      ) : null}
    </div>
  )
}

// Stable empties, so the store selectors above do not hand back a new array
// or object on every render.
const NO_IDS: readonly string[] = []
const NO_LABELS: Readonly<Record<string, string>> = {}

function speakerName(botId: string | null | undefined, roster: readonly CopilotBot[], zh: boolean): string {
  const bot = resolveBot(botId, roster)
  if (!bot) return zh ? '助手' : 'Assistant'
  return zh ? bot.title_zh : bot.title
}

function RoomEntry({
  entry,
  roster,
  projectId,
  zh,
  childTasks,
  onOpenRun,
  onOpenBot,
}: {
  entry: RoomEvent
  roster: readonly CopilotBot[]
  projectId: string
  zh: boolean
  childTasks: readonly RoomEvent[]
  onOpenRun?: (runId: string) => void
  onOpenBot?: (botId: string) => void
}) {
  if (entry.kind === 'handoff' && entry.handoff) {
    return (
      <article className="room-entry room-entry--handoff">
        <p className="room-entry-kind">{zh ? '交接' : 'Handover'}</p>
        <HandoffCard handoff={entry.handoff} bots={roster} onSelectOperator={onOpenBot} />
      </article>
    )
  }

  if (entry.kind === 'decision' && entry.decision) {
    return <DecisionCard decision={entry.decision} roster={roster} projectId={projectId} zh={zh} />
  }

  if (entry.kind === 'task' && entry.task) {
    const task = entry.task
    const owner = resolveBot(task.bot, roster)
    return (
      <article className="room-entry room-entry--task">
        <div className="room-entry-body">
          <p className="room-entry-kind">
            {zh ? '任务' : 'Task'} · {speakerName(task.bot, roster, zh)} · {roomTaskLabel(task, zh)}
          </p>
          <div className="room-task">
            {owner ? <BotAvatar id={owner.id} stance={owner.stance} /> : null}
            <div className="min-w-0">
              <p className="room-task-goal">{task.goal}</p>
              {onOpenRun ? (
                <Button type="button" variant="ghost" size="sm" onClick={() => onOpenRun(task.id)}>
                  {zh ? '查看交付' : 'Open delivery'}
                </Button>
              ) : null}
            </div>
          </div>
          {childTasks.length ? (
            <ul className="room-children">
              {childTasks.map((child) => (
                <li key={child.id}>
                  <span className="room-entry-kind">
                    {zh ? '委派给' : 'Delegated to'} {speakerName(child.task?.bot, roster, zh)} ·{' '}
                    {child.task ? roomTaskLabel(child.task, zh) : ''}
                  </span>
                  <span className="room-task-goal">{child.task?.goal}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </article>
    )
  }

  const message = entry.message
  if (!message) return null
  const mine = message.role === 'user'
  const bot = resolveBot(message.bot, roster)
  return (
    <article className={`room-entry${mine ? ' room-entry--mine' : ''}`}>
      {!mine && bot ? <BotAvatar id={bot.id} stance={bot.stance} /> : null}
      <div className="room-entry-body">
        <p className="room-speaker">
          {mine ? (zh ? '你' : 'You') : speakerName(message.bot, roster, zh)}
          {message.status === 'failed' ? ` · ${zh ? '未能回答' : 'could not answer'}` : ''}
        </p>
        <div className="room-text">{message.content}</div>
        <CopilotCitations
          citations={(message.citations ?? []) as Array<Record<string, unknown>>}
          projectId={projectId}
        />
      </div>
    </article>
  )
}

/**
 * A question an operator may not settle itself.
 *
 * The options are the substance: each carries the reason the operator gave and
 * the ids it rests on, and an option offered without a reason says so rather
 * than looking like the others. That is the whole difference between asking a
 * person to decide and asking them to approve.
 *
 * Answering writes a decision record attributed `agent_proposed_human_confirmed`
 * - the server does that, not this card. A 412 here means somebody else settled
 * it first, and the room reloads rather than overwriting their call.
 */
function DecisionCard({
  decision,
  roster,
  projectId,
  zh,
}: {
  decision: DecisionRequestResponse
  roster: readonly CopilotBot[]
  projectId: string
  zh: boolean
}) {
  const queryClient = useQueryClient()
  const readOnly = useCopilotReadOnly()
  const [failed, setFailed] = useState<string | null>(null)
  const settled = decision.status !== 'open'
  // The generated types make every defaulted list optional; normalised here
  // rather than at each use, as `CopilotChain` does for a handover's claims.
  const options = decision.options ?? []
  const chosen = options.find((option) => option.key === decision.answer)

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: copilotRoomQueryKey(projectId) })
    void queryClient.invalidateQueries({ queryKey: decisionRequestsQueryKey(projectId, 'open') })
    void queryClient.invalidateQueries({ queryKey: ['timeline', projectId] })
  }
  const explain = (error: unknown) => {
    // 412 is not an overwrite prompt: somebody else settled this question, and
    // the room reloads to show their call rather than replacing it. Detected on
    // the status like every other mutation here, not by reading the message.
    setFailed(
      error instanceof ApiError && error.status === 412
        ? zh ? '这个问题刚刚已被处理，请刷新后再看。' : 'This question was just settled by someone else; reload to see it.'
        : zh ? '没能提交你的决定，请重试。' : 'Your decision could not be saved. Try again.',
    )
  }
  const choose = useMutation({
    mutationFn: (key: string) => answerDecisionRequest(decision.id, decision.version, key),
    onSuccess: () => { setFailed(null); refresh() },
    onError: explain,
  })
  const drop = useMutation({
    mutationFn: () => withdrawDecisionRequest(decision.id, decision.version),
    onSuccess: () => { setFailed(null); refresh() },
    onError: explain,
  })
  const pending = choose.isPending || drop.isPending

  return (
    <article className="room-entry room-entry--decision">
      <div className="room-entry-body">
        <p className="room-entry-kind">
          {zh ? '需要你决定' : 'Your decision'} · {speakerName(decision.asked_by, roster, zh)}
        </p>
        <p className="room-decision-question">{decision.question}</p>
        <ul className="room-options">
          {options.map((option) => (
            <li key={option.key} className={option.key === decision.answer ? 'room-option room-option--chosen' : 'room-option'}>
              <div className="min-w-0">
                <p className="room-option-label">
                  {option.label}
                  {decision.recommended === option.key ? (
                    <span className="room-option-tag">{zh ? '操作员建议' : 'Suggested'}</span>
                  ) : null}
                </p>
                {option.rationale ? (
                  <p className="room-option-reason">{option.rationale}</p>
                ) : (
                  <p className="room-option-reason room-option-reason--absent">
                    {zh ? '没有给出理由' : 'No reason given'}
                  </p>
                )}
                {(option.evidence_refs ?? []).length ? (
                  <p className="room-option-refs">{(option.evidence_refs ?? []).join(' · ')}</p>
                ) : null}
              </div>
              {!settled && !readOnly ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  aria-label={`${zh ? '选择' : 'Choose'}: ${option.label}`}
                  disabled={pending}
                  onClick={() => choose.mutate(option.key)}
                >
                  {zh ? '选择' : 'Choose'}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
        {settled ? (
          <p className="room-decision-settled">
            {decision.status === 'answered'
              ? `${zh ? '已决定' : 'Decided'}: ${chosen?.label ?? decision.answer}`
              : zh ? '这个问题已撤回。' : 'This question was withdrawn.'}
          </p>
        ) : readOnly ? (
          <p className="room-decision-settled">
            {zh ? '只读模式：决定需要研究员权限。' : 'Read-only mode: settling this needs researcher access.'}
          </p>
        ) : (
          <Button type="button" variant="ghost" size="sm" disabled={pending} onClick={() => drop.mutate()}>
            {zh ? '这个问题不用回答了' : 'No longer needs an answer'}
          </Button>
        )}
        {failed ? (
          <Alert variant="destructive" className="mt-2">
            <AlertDescription>{failed}</AlertDescription>
          </Alert>
        ) : null}
      </div>
    </article>
  )
}
