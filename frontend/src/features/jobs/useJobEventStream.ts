import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { streamServerEvents } from '../../lib/api/sse'

/**
 * Watch every job that is still moving, and refresh what they change.
 *
 * `/jobs/{id}/events` existed since the compute path was built and had no
 * client; the drawer polled every three seconds instead, so a job that failed
 * at 0.1s looked healthy for another 2.9. The first version of this hook
 * streamed one job - whichever the drawer had selected, and only while it was
 * cancellable - which left a run of eight jobs updating on the timer for seven
 * of them, and the canvas updating on its own timer for all eight.
 *
 * Three properties are deliberate:
 *
 * **The stream is a hint, not a source of truth.** An event invalidates the
 * queries and the data is re-read through the ordinary SDK, so there is one
 * shape of job data in the app and a malformed frame cannot poison it.
 *
 * **Polling stays underneath.** `CLAUDE.md` puts it plainly - polling is the
 * floor and a dropped stream is not an error. The caller uses the returned flag
 * to slow its timer while a stream is connected, not to switch it off.
 *
 * **The number of connections is capped.** A run with forty parallel jobs would
 * otherwise open forty streams against a browser limit of six per host, and the
 * ones past the limit would sit queued, reporting nothing while looking live.
 */
export const MAX_JOB_STREAMS = 4

export function useJobEventStream(
  jobIds: readonly string[],
  workflowRunId: string | undefined,
): boolean {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(0)

  // A stable dependency: the array identity changes on every render of the
  // caller, and re-running this effect would tear down healthy streams.
  const watched = useMemo(
    () => [...jobIds].sort().slice(0, MAX_JOB_STREAMS).join(','),
    [jobIds],
  )

  useEffect(() => {
    const ids = watched ? watched.split(',') : []
    if (!ids.length || !workflowRunId) return
    const controller = new AbortController()
    let live = 0
    const adjust = (delta: number) => {
      live += delta
      setOpen(live)
    }

    for (const id of ids) {
      adjust(1)
      void streamServerEvents(`/jobs/${id}/events`, {
        signal: controller.signal,
        onEvent: () => {
          // The job list, this job's logs, and the canvas: a node's status on
          // the graph is a job's status, and leaving the graph to its own timer
          // was why a finished stage stayed amber for three seconds.
          void queryClient.invalidateQueries({ queryKey: ['workflow-jobs', workflowRunId] })
          void queryClient.invalidateQueries({ queryKey: ['job-logs', id] })
          void queryClient.invalidateQueries({ queryKey: ['workflow-graph', workflowRunId] })
        },
      })
        // A refused or dropped stream is not reported: the caller's polling is
        // still running, so this degrades to the behaviour that existed before.
        .catch(() => {})
        .finally(() => adjust(-1))
    }

    return () => {
      controller.abort()
      setOpen(0)
    }
  }, [watched, workflowRunId, queryClient])

  return open > 0
}
