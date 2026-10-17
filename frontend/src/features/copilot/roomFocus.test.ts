import { expect, it } from 'vitest'
import type { RoomEvent } from '../../lib/api/generated'
import { focusRoom } from './roomFocus'

const messageDefaults = { id: 'message', conversation_id: 'conversation', citations: [], tool_calls: [],
  created_at: '2026-10-16T10:00:00Z', updated_at: '2026-10-16T10:00:00Z', error: null, version: 1 }

it('keeps archived pending messages in history when the audit view is loaded', () => {
  const archived = { kind: 'message', id: 'archived', occurred_at: '2026-10-16T10:00:00Z',
    message: { ...messageDefaults, role: 'assistant', status: 'pending', content: '', context: { chat_archive: { archived: true } } } } as RoomEvent
  const pending = { kind: 'message', id: 'pending', occurred_at: '2026-10-16T11:00:00Z',
    message: { ...messageDefaults, role: 'assistant', status: 'pending', content: '', context: {} } } as RoomEvent
  const focused = focusRoom([archived, pending])
  expect(focused.current).toEqual([pending])
  expect(focused.history).toEqual([archived])
})
