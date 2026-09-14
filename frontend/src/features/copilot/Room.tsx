import { useEffect, useRef } from 'react'
import { PaperPlaneTiltIcon, SpinnerGapIcon } from '@phosphor-icons/react'
import { useQueryClient } from '@tanstack/react-query'
import type { RoomEvent } from '../../lib/api/generated'
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
