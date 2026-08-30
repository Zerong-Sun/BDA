import { getTranslations } from '../../lib/i18n'
import { matchSkill } from './skills/registry'
import { streamCopilotMessage, toCopilotApiMessages } from '../../lib/api/copilot'
import { legacyCopilotIntro, useAppStore, type CopilotChatMessage } from '../../lib/store/appStore'
import { detectReviewIntent } from '../research/reviewIntent'
import { useEffect, useState } from 'react'

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
  const [loading, setLoading] = useState(false)
  const [loadingStage, setLoadingStage] = useState<CopilotLoadingStage>('idle')
  const [loadingDetail, setLoadingDetail] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastMode, setLastMode] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null
    return sessionStorage.getItem('bda_copilot_last_mode')
  })
  const usableMessages = messages.filter(
    (message) => message.content.trim().length > 0 && message.content !== legacyCopilotIntro,
  )

  const send = async (input: string) => {
    const trimmed = input.trim()
    if (!trimmed || loading) return

    const skill = matchSkill(trimmed)?.name
    const reviewIntent = detectReviewIntent(trimmed)
    const nextMessages: CopilotChatMessage[] = [
      ...usableMessages,
      {
        role: 'user',
        content: trimmed,
        ...(reviewIntent ? { meta: { reviewIntent: true } } : {}),
      },
    ]
    setMessages(nextMessages)
    setLoading(true)
    setLoadingStage('connecting')
    setLoadingDetail(null)
    setError(null)

    const scopedMessages = nextMessages.slice(-MAX_COPILOT_HISTORY)
    const contextParams = new URLSearchParams((pageContext ?? '').replace(/;\s*/g, '&'))

    const payload = {
      messages: toCopilotApiMessages(scopedMessages),
      project_id: projectId,
      skill,
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
      setMessages((prev) => [...prev, { role: 'assistant', content: '' }])
      const accepted = await streamCopilotMessage(payload, (chunk) => {
        streamed += chunk
        setMessages((prev) => {
          const copy = [...prev]
          copy[copy.length - 1] = { role: 'assistant', content: streamed }
          return copy
        })
      }, (stage) => {
        if (stage.startsWith('tool:')) {
          setLoadingStage('tool')
          setLoadingDetail(stage.slice('tool:'.length).replace(/[_-]+/g, ' '))
          return
        }
        if (stage === 'done') {
          setLoadingStage('idle')
        } else if (stage === 'connecting' || stage === 'thinking' || stage === 'streaming') {
          setLoadingStage(stage)
        }
        if (stage !== 'thinking') setLoadingDetail(null)
        if (stage === 'done' && typeof window !== 'undefined') {
          const mode = sessionStorage.getItem('bda_copilot_last_mode')
          if (mode) setLastMode(mode)
        }
      }, (message) => {
        setMessages((prev) => {
          const copy = [...prev]
          copy[copy.length - 1] = {
            role: 'assistant',
            content: message.content,
            meta: { citations: message.citations, toolCalls: message.tool_calls },
          }
          return copy
        })
      })
      if (projectId) setConversationId(projectId, accepted.conversationId)
      setSelectedEntityIds([])
      if (!streamed) throw new Error('Copilot completed without an assistant response.')
    } catch (err) {
      const message = explainCopilotError(err)
      setError(message)
      setMessages((prev) => {
        const copy = [...prev]
        copy[copy.length - 1] = {
          role: 'assistant',
          content: message,
        }
        return copy
      })
    } finally {
      setLoading(false)
      setLoadingStage('idle')
      setLoadingDetail(null)
    }
  }

  return { messages: usableMessages, loading, loadingStage, loadingDetail, error, send, resetMessages, lastMode }
}
