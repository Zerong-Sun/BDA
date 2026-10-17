import type { RoomEvent } from '../../lib/api/generated'
import { LIVE_RUN_STATUSES } from '../../lib/api/agentRuns'

export function isArchived(entry: RoomEvent): boolean {
  const archive = entry.message?.context?.chat_archive
  return typeof archive === 'object' && archive !== null && 'archived' in archive && archive.archived === true
}

function isLaunchNotice(entry: RoomEvent): boolean {
  return Boolean(entry.message?.tool_calls?.some((call) =>
    typeof call === 'object' && call !== null && 'name' in call && call.name === 'start_team_task'
    && 'status' in call && call.status === 'completed'))
}

/** Presentation only: no text matching, deletion or scientific summarization. */
export function focusRoom(entries: readonly RoomEvent[]) {
  const newest = [...entries].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at) || b.id.localeCompare(a.id))
  const conclusion = newest.find((entry) => !isArchived(entry) && (
    (entry.message?.role === 'assistant' && entry.message.status === 'completed' && entry.message.content.trim() && !isLaunchNotice(entry))
    || (entry.discussion?.is_delivery && !entry.discussion.parent_run_id)
  ))
  const latestTask = newest.find((entry) => entry.task && !entry.task.parent_run_id)
  const focusIds = new Set<string>()
  if (conclusion) focusIds.add(`${conclusion.kind}-${conclusion.id}`)
  // Never fold a live task or unanswered decision into history.
  for (const entry of entries) {
    if (isArchived(entry)) continue
    if ((entry.task && (LIVE_RUN_STATUSES as readonly string[]).includes(entry.task.status))
      || entry.decision?.status === 'open' || entry.message?.status === 'pending') {
      focusIds.add(`${entry.kind}-${entry.id}`)
    }
  }
  for (const entry of entries) {
    if (entry.task?.parent_run_id && focusIds.has(`task-${entry.id}`)) focusIds.add(`task-${entry.task.parent_run_id}`)
  }
  // Keep the latest unanswered question / failure visible, without dragging its
  // earlier conversation or background revisions into the default view.
  const lastMessage = newest.find((entry) => entry.message && !isArchived(entry) && !isLaunchNotice(entry))
  if (lastMessage && (!conclusion || lastMessage.occurred_at >= conclusion.occurred_at)) focusIds.add(`message-${lastMessage.id}`)
  return {
    conclusion,
    latestTask,
    current: entries.filter((entry) => focusIds.has(`${entry.kind}-${entry.id}`) && entry !== conclusion),
    history: entries.filter((entry) => !focusIds.has(`${entry.kind}-${entry.id}`)),
  }
}

/** Only recorded review evidence can mark an answer reviewed. */
export function conclusionReview(entry: RoomEvent | undefined): 'completed' | 'incomplete' | 'unknown' {
  if (!entry) return 'unknown'
  if (entry.discussion?.scientific_review === 'automated_review_completed') return 'completed'
  if (entry.discussion?.scientific_review === 'unavailable' || entry.message?.context?.review_status === 'not_completed') return 'incomplete'
  const review = entry.message?.tool_calls?.find((call): call is { name: string; status: string } =>
    typeof call === 'object' && call !== null && 'name' in call && call.name === 'grounded_scientific_review' && 'status' in call && typeof call.status === 'string')
  if (review?.status === 'completed') return 'completed'
  if (review?.status === 'blocked' || review?.status === 'failed') return 'incomplete'
  return 'unknown'
}
