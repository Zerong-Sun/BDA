import { API_BASE, authToken } from './client'

/**
 * Reading a server-sent event stream.
 *
 * Not `EventSource`. The streaming endpoints authenticate with a bearer token and
 * `EventSource` cannot set headers, so the alternatives would be putting the access
 * token in the query string - where proxies log it - or leaving two working stream
 * endpoints with no client, which is what happened. `fetch` keeps the token in a
 * header, at the cost of parsing frames here.
 *
 * There is no automatic reconnection. A dropped stream is reported to the caller so
 * it can fall back to polling, which every caller here can already do: a silent
 * reconnect loop would turn "the server went away" into "nothing is happening", and
 * that is precisely the failure the Activity surface exists to make visible.
 */

export interface ServerSentEvent {
  event: string
  data: string
  id?: string
}

export interface StreamOptions {
  /** Called per frame. Throwing from it stops the stream. */
  onEvent: (event: ServerSentEvent) => void
  signal?: AbortSignal
}

function parseFrame(raw: string): ServerSentEvent | null {
  const lines = raw.split(/\r?\n/)
  const data = lines
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).replace(/^ /, ''))
    .join('\n')
  if (!data) return null
  const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim() || 'message'
  const id = lines.find((line) => line.startsWith('id:'))?.slice(3).trim()
  return { event, data, id }
}

/**
 * Consume `path` until the server closes it, `signal` aborts, or it fails.
 *
 * Resolves when the stream ends normally. Rejects on anything else, including a
 * non-2xx open - the caller decides whether that is fatal or a reason to poll.
 */
export async function streamServerEvents(path: string, { onEvent, signal }: StreamOptions): Promise<void> {
  const token = authToken()
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    headers: {
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`Stream ${path} failed to open (${response.status})`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) return
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split(/\r?\n\r?\n/)
      // The tail is whatever has not been terminated by a blank line yet.
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        const parsed = parseFrame(frame)
        if (parsed) onEvent(parsed)
      }
    }
  } finally {
    // Releasing the lock lets the body be cancelled by an aborted signal rather
    // than leaving the connection open until the tab closes.
    reader.releaseLock()
  }
}
