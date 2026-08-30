import { JobSchema, type Job } from '../schemas/job'
import {
  cancelJobApiV2JobsJobIdCancelPost,
  getJobApiV2JobsJobIdGet,
  getJobLogsApiV2JobsJobIdLogsGet,
  listWorkflowJobsApiV2WorkflowRunsWorkflowIdJobsGet,
  retryFailedJobApiV2JobsJobIdRetryPost,
} from './generated/sdk.gen'
import './generatedTransport'

export function listWorkflowJobs(workflowRunId: string): Promise<Job[]> {
  return listWorkflowJobsApiV2WorkflowRunsWorkflowIdJobsGet<true>({ path: { workflow_id: workflowRunId },
    throwOnError: true }).then(({ data }) =>
    data.items.map((item) => JobSchema.parse(item)),
  )
}

export function getJob(jobId: string): Promise<Job> {
  return getJobApiV2JobsJobIdGet<true>({ path: { job_id: jobId }, throwOnError: true })
    .then(({ data }) => JobSchema.parse(data))
}

export function syncJobResult(jobId: string): Promise<{
  job: Job
  live_status: string
  outputs?: Record<string, unknown> | null
  next_actions?: string[]
}> {
  return getJob(jobId).then((job) => ({ job, live_status: job.status, outputs: null }))
}

export function getJobLogs(jobId: string, tail = 200): Promise<{ job_id: string; logs: string }> {
  return getJobLogsApiV2JobsJobIdLogsGet<true>({ path: { job_id: jobId },
    query: { limit: Math.min(tail, 200) }, throwOnError: true,
  }).then(({ data: page }) => ({ job_id: jobId, logs: page.items.map((entry) =>
    `${entry.created_at} [${entry.level}] ${entry.message}`).join('\n') }))
}

export function cancelJob(jobId: string): Promise<{ job_id: string; status: string; cancelled?: boolean }> {
  return cancelJobApiV2JobsJobIdCancelPost<true>({ path: { job_id: jobId }, throwOnError: true })
    .then(({ data: response }) => ({ job_id: response.id, status: response.status, cancelled: true }))
}

/**
 * Resubmit a failed or cancelled job as a fresh attempt.
 *
 * The server refuses anything else with 409, inherits the original submission's
 * timeout budget, and returns the *new* job - a retry is a new row, not a revived one,
 * so the failure that prompted it stays on the record.
 */
export function retryJob(jobId: string): Promise<Job> {
  return retryFailedJobApiV2JobsJobIdRetryPost<true>({ path: { job_id: jobId }, throwOnError: true })
    .then(({ data }) => JobSchema.parse(data))
}
