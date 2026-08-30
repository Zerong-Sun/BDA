import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { streamServerEvents } from '../../lib/api/sse'

/**
 * Refresh a workflow's job list the moment one of its jobs changes state.
 *
 * `/jobs/{id}/events` has existed since the compute path was built and had no client,
 * while `CLAUDE.md` described job status as coming from it. The drawer polled every
 * three seconds instead, so a job that failed at 0.1s looked healthy for another 2.9.
 *
 * The stream is used as a *hint*, not as a source of truth: an event invalidates the
 * job query and the list is re-read through the ordinary SDK. That keeps one shape of
 * job data in the app, and means a stream that never arrives - a buffering proxy, an
 * idle timeout - costs nothing beyond the polling that is still underneath it.
 */
export function useJobEventStream(jobId: string | null, workflowRunId: string | undefined): void {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!jobId || !workflowRunId) return
    const controller = new AbortController()

    void streamServerEvents(`/jobs/${jobId}/events`, {
      signal: controller.signal,
      onEvent: () => {
        void queryClient.invalidateQueries({ queryKey: ['workflow-jobs', workflowRunId] })
        void queryClient.invalidateQueries({ queryKey: ['job-logs', jobId] })
      },
      // Failure is not reported: polling still runs, so a dropped stream degrades to
      // the behaviour that existed before rather than to an error the user must read.
    }).catch(() => {})

    return () => controller.abort()
  }, [jobId, workflowRunId, queryClient])
}
