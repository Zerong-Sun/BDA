import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { streamServerEvents } from '../api/sse'

/** One project stream per app shell, independent of how many views use its data. */
export function useProjectEvents(projectId: string | null | undefined) {
  const client = useQueryClient()
  useEffect(() => {
    if (!projectId) return
    let stopped = false
    let controller: AbortController | undefined
    let reconnect: ReturnType<typeof setTimeout> | undefined
    let generation = 0
    let lastFrame = 0
    let lastRevision: string | undefined
    const invalidate = () => {
      for (const key of [
        ['copilot', 'room', projectId], ['copilot', 'handoffs', projectId],
        ['copilot', 'decision-requests', projectId], ['agent-runs', projectId],
        ['cluster-drafts', projectId], ['literature-claims', projectId],
      ]) void client.invalidateQueries({ queryKey: key })
    }
    const connect = () => {
      if (stopped || document.hidden) return
      const attempt = ++generation
      controller?.abort()
      controller = new AbortController()
      void streamServerEvents(`/copilot/projects/${encodeURIComponent(projectId)}/events`, {
        signal: controller.signal,
        onEvent: (event) => {
          if (stopped || attempt !== generation || controller?.signal.aborted) return
          lastFrame = Date.now()
          if (event.event !== 'project-change') return
          const payload = JSON.parse(event.data) as { project_id?: string }
          if (payload.project_id !== projectId) return
          if (event.id !== lastRevision || !event.id) invalidate()
          lastRevision = event.id
        },
      }).catch(() => {}).finally(() => {
        if (!stopped && attempt === generation && !document.hidden) reconnect = setTimeout(connect, 15_000)
      })
    }
    const visibility = () => {
      clearTimeout(reconnect)
      if (document.hidden) { generation++; controller?.abort() }
      else { invalidate(); connect() }
    }
    // Independent fallback covers both failed streams and silent proxy buffering.
    const polling = setInterval(() => {
      if (!document.hidden && Date.now() - lastFrame > 15_000) invalidate()
    }, 30_000)
    document.addEventListener('visibilitychange', visibility)
    connect()
    return () => {
      stopped = true
      controller?.abort()
      clearTimeout(reconnect)
      clearInterval(polling)
      document.removeEventListener('visibilitychange', visibility)
    }
  }, [client, projectId])
}
