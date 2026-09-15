import { getTranslations } from '../../lib/i18n'
import { matchBot, useCopilotBots } from './bots/registry'
import { copilotHandoffsQueryKey } from './handoffs'
import { getLatestCopilotMode, streamCopilotMessage, toCopilotApiMessages } from '../../lib/api/copilot'
import { legacyCopilotIntro, useAppStore, type CopilotChatMessage } from '../../lib/store/appStore'
import { detectReviewIntent } from '../research/reviewIntent'
import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { requireCopilotWrite } from './commandAccess'

const MAX_COPILOT_HISTORY = 20
export type CopilotLoadingStage = 'idle' | 'connecting' | 'thinking' | 'tool' | 'streaming'

function explainCopilotError(err: unknown): string {
  const { t, format } = getTranslations()
  const e = t.copilot.errors
  const raw = err instanceof Error ? err.message : e.requestFailed
  if (raw.includes('Failed to fetch') || raw.includes('NetworkError')) {
    return e.connectionFailed
  }
  if (raw.includes('401')) return e.sessionExpired
  if (raw.includes('403')) return e.projectUnavailable
  if (raw.includes('429')) return e.rateLimited
  if (raw.includes('502') || raw.includes('503') || raw.includes('504')) {
    return e.serviceUnavailable
  }
  return format(e.requestFailedWithReason, { reason: raw })
}

export function useCopilotChat(projectId?: string, pageContext?: string, language: 'en' | 'zh' = 'en') {
  const queryClient = useQueryClient()
  const session = useAppStore((state) => projectId ? state.copilotSessions[projectId] : undefined)
  const legacyMessages = useAppStore((state) => state.copilotMessages)
  const messages = session?.messages ?? legacyMessages
  const conversationId = session?.conversationId ?? null
  const setLegacyMessages = useAppStore((state) => state.setCopilotMessages)
  const setSessionMessages = useAppStore((state) => state.setCopilotSessionMessages)
  const setConversationId = useAppStore((state) => state.setCopilotConversationId)
  const resetSession = useAppStore((state) => state.resetCopilotSession)
  const setSelectedEntityIds = useAppStore((state) => state.setCopilotSelectedEntityIds)
  const setMessages = (
    next: CopilotChatMessage[] | ((messages: CopilotChatMessage[]) => CopilotChatMessage[]),
  ) => {
    const state = useAppStore.getState()
    const current = projectId
      ? state.copilotSessions[projectId]?.messages ?? state.copilotMessages
      : state.copilotMessages
    const resolved = typeof next === 'function' ? next(current) : next
    if (projectId) setSessionMessages(projectId, resolved)
    else setLegacyMessages(resolved)
  }
  const resetMessages = () => {
    if (projectId) resetSession(projectId)
    else setLegacyMessages([])
  }
  useEffect(() => {
    if (!projectId) return
    const state = useAppStore.getState()
    const existing = state.copilotSessions[projectId]
    if (existing) return
    const migratedMessages = state.copilotMessages
    setSessionMessages(projectId, migratedMessages)
    setLegacyMessages([])
  }, [projectId, setLegacyMessages, setSessionMessages])
  const loading = Boolean(session?.pending)
  const loadingStage: CopilotLoadingStage = session?.pending?.stage ?? 'idle'
  const loadingDetail = session?.pending?.detail ?? null
  const error = session?.error ?? null
  const setRequest = useAppStore((state) => state.setCopilotSessionRequest)
  const [lastMode, setLastMode] = useState<string | null>(() => getLatestCopilotMode())
  // null means "let the message decide". Kept in the project's session rather
  // than in component state: the drawer unmounts every time it closes, and a
  // phase of work is several messages long, so component state quietly sent the
  // operator back to Auto whenever the user looked at a page.
  const bot = session?.bot ?? null
  const setSessionBot = useAppStore((state) => state.setCopilotSessionBot)
  const setBot = (next: string | null) => {
    if (projectId) setSessionBot(projectId, next)
  }
  const { data: bots } = useCopilotBots()
  const usableMessages = messages.filter(
    (message) => message.content.trim().length > 0 && message.content !== legacyCopilotIntro,
  )

  /**
   * One turn. `options.bot` addresses a single message to one operator - the
   * room's `@mention` - and is deliberately not stored: pinning the
   * conversation to whoever was addressed once would re-route everything after
   * it, which is not what naming somebody in a room means.
   */
  const send = async (input: string, options?: { bot?: string }) => {
    const trimmed = input.trim()
    if (!trimmed || !projectId || useAppStore.getState().copilotSessions[projectId]?.pending) return
    try { requireCopilotWrite() } catch { return }
    const requestId = crypto.randomUUID()
    setRequest(projectId, { id: requestId, stage: 'connecting', detail: null }, null)
    // A reset, deletion or sign-out invalidates this request. A remount keeps it
    // alive and sees the same lock, so concurrent replies cannot overwrite it.
    const isCurrent = () => useAppStore.getState().copilotSessions[projectId]?.pending?.id === requestId
    const writeMessages = (next: CopilotChatMessage[] | ((messages: CopilotChatMessage[]) => CopilotChatMessage[])) => {
      if (isCurrent()) setMessages(next)
    }
    const updateStage = (stage: Exclude<CopilotLoadingStage, 'idle'>, detail: string | null = null) => {
      if (isCurrent()) setRequest(projectId, { id: requestId, stage, detail })
    }

    // One narrowing hint, derived from the served roster. There used to be a
    // second - a hand-written capability list in `skills/registry.ts` with its
    // own bilingual triggers, consulted when no bot matched. It was a copy of
    // the backend's capability ids maintained beside the roster that already
    // describes the same routing, and a copy is what drifts: its `systemPrompt`
    // field was populated for all nine entries and read by nothing. Its
    // vocabulary now lives on the operators that own it.
    // An address for this turn, then the operator the room is scoped to, then
    // the served roster's own triggers. Each is a narrowing hint the server
    // intersects with the project's capabilities; none of them can widen a turn.
    const activeBot = options?.bot ?? bot ?? matchBot(trimmed, bots ?? [])?.id
    const reviewIntent = detectReviewIntent(trimmed)
    const nextMessages: CopilotChatMessage[] = [
      ...usableMessages,
      {
        role: 'user',
        content: trimmed,
        ...(reviewIntent ? { meta: { reviewIntent: true } } : {}),
      },
    ]
    writeMessages(nextMessages)

    const scopedMessages = nextMessages.slice(-MAX_COPILOT_HISTORY)
    const contextParams = new URLSearchParams((pageContext ?? '').replace(/;\s*/g, '&'))

    const payload = {
      messages: toCopilotApiMessages(scopedMessages),
      project_id: projectId,
      // `skill` stays on the request contract - an agent run, an MCP grant or
      // another client may still narrow to one capability - and this UI simply
      // no longer guesses one. Sending neither means the project's configured
      // set, which is the documented undifferentiated case.
      bot: activeBot,
      conversation_id: conversationId,
      intent: reviewIntent ? 'review_section' as const : 'chat' as const,
      context: {
        route: contextParams.get('route') ?? undefined,
        research_tab: contextParams.get('research_tab') ?? undefined,
        selected_entity_ids: contextParams.getAll('entity'),
        language,
      },
    }

    try {
      let streamed = ''
      writeMessages((prev) => [...prev, { role: 'assistant', content: '' }])
      const accepted = await streamCopilotMessage(payload, (chunk) => {
        streamed += chunk
        writeMessages((prev) => {
          const copy = [...prev]
          copy[copy.length - 1] = { role: 'assistant', content: streamed }
          return copy
        })
      }, (stage) => {
        if (!isCurrent()) return
        if (stage.startsWith('tool:')) updateStage('tool', stage.slice('tool:'.length).replace(/[_-]+/g, ' '))
        else if (stage === 'connecting' || stage === 'thinking' || stage === 'streaming') updateStage(stage)
        else if (stage === 'done') {
          const mode = getLatestCopilotMode()
          if (mode) setLastMode(mode)
        }
      }, (message) => {
        if (!isCurrent()) return
        writeMessages((prev) => {
          const copy = [...prev]
          copy[copy.length - 1] = {
            role: 'assistant',
            content: message.content,
            meta: { citations: message.citations, toolCalls: message.tool_calls },
          }
          return copy
        })
        // A turn that recorded a handover changed the chain, and a Chain tab
        // left open beside the conversation would go on showing the one before
        // it. Keyed on the tool actually called rather than invalidated every
        // turn, because most turns do not touch the record.
        if ((message.tool_calls ?? []).some((call) => call?.name === 'post_handoff')) {
          void queryClient.invalidateQueries({ queryKey: copilotHandoffsQueryKey(projectId ?? null) })
        }
      })
      if (!isCurrent()) return
      setConversationId(projectId, accepted.conversationId)
      const currentSources = useAppStore.getState().copilotSessions[projectId]?.selectedEntityIds ?? []
      const sentSources = payload.context.selected_entity_ids
      if (currentSources.length === sentSources.length && currentSources.every((id, index) => id === sentSources[index])) setSelectedEntityIds([], projectId)
      if (!streamed) throw new Error('Copilot completed without an assistant response.')
    } catch (err) {
      if (!isCurrent()) return
      const message = explainCopilotError(err)
      writeMessages((prev) => {
        const copy = [...prev]
        copy[copy.length - 1] = {
          role: 'assistant',
          content: message,
        }
        return copy
      })
      setRequest(projectId, null, message)
    } finally {
      if (isCurrent()) setRequest(projectId, null)
    }
  }

  return {
    messages: usableMessages, loading, loadingStage, loadingDetail, error, send, resetMessages,
    lastMode, bots: bots ?? [], bot, setBot,
  }
}
