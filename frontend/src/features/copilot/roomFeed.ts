import { useQuery } from '@tanstack/react-query'
import { readRoomApiV2CopilotProjectsProjectIdRoomGet } from '../../lib/api/generated'
import type { RoomEvent } from '../../lib/api/generated'
import { LIVE_RUN_STATUSES } from '../../lib/api/agentRuns'

/**
 * Reading the project's room.
 *
 * Its own module rather than living beside the view, because a component file
 * may export only components here - the same split `handoffs.ts` and
 * `bots/registry.ts` already make. Named `roomFeed` and not `room` because
 * `Room.tsx` sits beside it, and two modules differing only in case are one
 * file on a case-insensitive filesystem.
 *
 * The room is server state, not session state. The chat drawer keeps its
 * transcript in the store, which is why a reload used to empty it; entries here
 * survive a reload because they are the rows themselves.
 */

export const copilotRoomQueryKey = (projectId: string | null) =>
  ['copilot', 'room', projectId] as const

/** A task entry that can still move on its own, so the room keeps looking. */
function isLiveEntry(entry: RoomEvent): boolean {
  return Boolean(entry.task && (LIVE_RUN_STATUSES as readonly string[]).includes(entry.task.status))
}

export function useCopilotRoom(projectId: string | null, limit = 100) {
  return useQuery({
    // The project id is part of the key because a room belongs to one project
    // and nothing else; a shared key would show one project's chain in another.
    queryKey: copilotRoomQueryKey(projectId),
    enabled: Boolean(projectId),
    queryFn: async () => {
      const { data } = await readRoomApiV2CopilotProjectsProjectIdRoomGet<true>({
        throwOnError: true,
        path: { project_id: projectId as string },
        query: { limit },
      })
      return data.items
    },
    // Messages arrive over the chat stream and are refetched when a turn ends.
    // A task moves because a worker moved it, with nothing to stream here, so a
    // room holding a live task polls - and stops as soon as none is live.
    refetchInterval: (query) => (query.state.data ?? []).some(isLiveEntry) ? 4000 : false,
  })
}

/**
 * Entries oldest first: a room is read downwards, and the API answers newest
 * first because that is what paging a growing list requires.
 */
export function inReadingOrder(entries: readonly RoomEvent[]): RoomEvent[] {
  return [...entries].reverse()
}

/**
 * Child tasks grouped under the entry that opened them.
 *
 * A delegated run is work one operator asked another for; listing it at the top
 * level would show work arriving from nowhere, and the delegation - the only
 * real operator-to-operator action besides a handover - would be invisible.
 */
export function childTasksByParent(entries: readonly RoomEvent[]): Map<string, RoomEvent[]> {
  const children = new Map<string, RoomEvent[]>()
  for (const entry of entries) {
    const parent = entry.task?.parent_run_id
    if (!parent) continue
    children.set(parent, [...(children.get(parent) ?? []), entry])
  }
  return children
}

/** Top-level entries: everything except the delegated children nested above. */
export function topLevelEntries(entries: readonly RoomEvent[]): RoomEvent[] {
  return entries.filter((entry) => !entry.task?.parent_run_id)
}
