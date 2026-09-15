import { ModelResultGuide } from '../results/ModelResultGuide'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowsClockwise, Download, StopCircle, Terminal } from '@phosphor-icons/react'
import { cancelJob, getJobLogs, listWorkflowJobs, retryJob, syncJobResult } from '../../lib/api/jobs'
import { AttachToGoalButton } from '../research/AttachToGoalButton'
import { useJobEventStream } from './useJobEventStream'
import type { Job } from '../../lib/schemas/job'
import { isCancellableJob, isRetryableJob, isSettledJob } from '../../lib/schemas/workflow'
import { StatusPill } from '../../components/ui/StatusPill'
import { statusTone } from '../../components/ui/statusTone'
import { RecordDecisionButton } from '../timeline/RecordDecisionButton'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Frame, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'
import {
  Timeline,
  TimelineContent,
  TimelineIndicator,
  TimelineItem,
  TimelineSeparator,
  TimelineTitle,
} from '../../components/reui/timeline'
import { Button } from '../../components/ui/Button'
import { ScrollArea } from '../../components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../../components/ui/sheet'

interface JobStatusDrawerProps {
  workflowRunId?: string
  selectedNodeId?: string | null
  readOnly?: boolean
}

/** How often to ask when nothing is streaming, and when something is. */
const POLL_WHILE_BLIND_MS = 3000
const POLL_BEHIND_STREAM_MS = 15_000

export function JobStatusDrawer({ workflowRunId, readOnly = false, selectedNodeId }: JobStatusDrawerProps) {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const showToast = useToastStore((s) => s.show)
  const { t, format } = useI18n()
  // The timer reads this rather than the flag directly: the queries below are
  // declared before the stream they depend on, and a poll is a floor whose
  // exact period nobody is waiting on - an effect updates it in time.
  const pollMs = useRef(POLL_WHILE_BLIND_MS)

  const { data: jobs = [] } = useQuery({
    queryKey: ['workflow-jobs', workflowRunId],
    queryFn: () => listWorkflowJobs(workflowRunId!),
    enabled: Boolean(workflowRunId),
    refetchInterval: (query) => {
      const data = query.state.data ?? []
      // Anything not terminal is still moving. The previous list named 'staging' and
      // 'collecting_outputs', which no longer exist, and omitted 'pending', 'dispatching'
      // and 'collecting' - so the list stopped refreshing exactly while work was starting.
      return data.some((job) => isCancellableJob(job.status)) ? pollMs.current : false
    },
  })

  const visibleJobs = useMemo(() => {
    if (!selectedNodeId) return jobs
    return jobs.filter((job) => job.workflow_node_id === selectedNodeId)
  }, [jobs, selectedNodeId])

  const selectedJob = visibleJobs.find((job) => job.id === selectedJobId) ?? null

  // Every job that is still moving, not only the one on screen: a run's other
  // stages change the canvas and the list too, and watching one of eight left
  // the rest on the timer. Polling below is still the floor.
  const liveJobIds = useMemo(
    () => jobs.filter((job) => isCancellableJob(job.status)).map((job) => job.id),
    [jobs],
  )
  const streaming = useJobEventStream(liveJobIds, workflowRunId)
  useEffect(() => {
    pollMs.current = streaming ? POLL_BEHIND_STREAM_MS : POLL_WHILE_BLIND_MS
  }, [streaming])

  const { data: logPayload } = useQuery({
    queryKey: ['job-logs', selectedJob?.id],
    queryFn: () => getJobLogs(selectedJob!.id),
    enabled: Boolean(selectedJob?.id),
    // A callback, like the jobs query's: the period is read when the timer is
    // scheduled, not during render.
    refetchInterval: () => (selectedJob && isCancellableJob(selectedJob.status) ? pollMs.current : false),
  })

  const cancel = useMutation({
    mutationFn: (job: Job) => {
      if (readOnly) throw new Error(t.workflowExt.canvas.readOnlyBanner)
      return cancelJob(job.id)
    },
    onSuccess: () => {
      showToast(t.jobs.cancelRequested, 'info')
      queryClient.invalidateQueries({ queryKey: ['workflow-jobs', workflowRunId] })
    },
    onError: () => showToast(t.jobs.cancelFailed, 'error'),
  })

  const retry = useMutation({
    mutationFn: (job: Job) => {
      if (readOnly) throw new Error(t.workflowExt.canvas.readOnlyBanner)
      return retryJob(job.id)
    },
    onSuccess: () => {
      // A retry is a new job row, so the list is what changed - not this one.
      showToast(t.jobs.retryRequested, 'info')
      queryClient.invalidateQueries({ queryKey: ['workflow-jobs', workflowRunId] })
    },
    onError: (err) =>
      showToast(err instanceof Error ? err.message : t.jobs.retryFailed, 'error'),
  })

  const syncResult = useMutation({
    mutationFn: (job: Job) => {
      if (readOnly) throw new Error(t.workflowExt.canvas.readOnlyBanner)
      return syncJobResult(job.id)
    },
    onSuccess: async (result) => {
      const artifacts = Array.isArray(result.outputs?.artifacts) ? result.outputs.artifacts.length : 0
      const message =
        result.outputs?.manifest_found === true
          ? format(artifacts === 1 ? t.jobs.syncedArtifacts : t.jobs.syncedArtifactsPlural, { count: artifacts })
          : format(t.jobs.jobStatusNoManifest, { status: result.live_status })
      showToast(message, result.outputs?.manifest_found === true ? 'success' : 'info')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['workflow-jobs', workflowRunId] }),
        queryClient.invalidateQueries({ queryKey: ['job-logs', result.job.id] }),
        queryClient.invalidateQueries({ queryKey: ['workflow-graph', workflowRunId] }),
        queryClient.invalidateQueries({ queryKey: ['project-artifacts'] }),
        queryClient.invalidateQueries({ queryKey: ['candidates'] }),
      ])
    },
    onError: (error) => showToast(error instanceof Error ? error.message : t.jobs.syncFailed, 'error'),
  })

  return (
    <Frame variant="inverse" spacing="xs">
      <FrameHeader className="flex-row items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-accent">{t.jobs.title}</p>
          <FrameTitle>
            {selectedNodeId ? t.jobs.selectedNodeRuns : t.jobs.workflowRuns}
          </FrameTitle>
        </div>
        <Button type="button"
          variant="ghost"
          size="icon-xs"
          onClick={() => queryClient.invalidateQueries({ queryKey: ['workflow-jobs', workflowRunId] })}
          title={t.jobs.refreshTitle}
        >
          <ArrowsClockwise className="h-3.5 w-3.5" />
        </Button>
      </FrameHeader>
      <FramePanel>

      <div className="mb-3 rounded-md border border-border-soft bg-surface-1 p-2">
        <p className="text-xs leading-relaxed text-text-secondary">{t.jobs.manualSubmitHint}</p>
      </div>

      {visibleJobs.length === 0 ? (
        <Alert>
          <AlertDescription>{t.jobs.noJobs}</AlertDescription>
        </Alert>
      ) : (
        <div className="space-y-2">
          {visibleJobs.map((job) => (
            <Button type="button"
              key={job.id}
              variant={selectedJob?.id === job.id ? 'secondary' : 'outline'}
              className={`h-auto w-full flex-col items-stretch rounded-md border p-2 text-left whitespace-normal ${
                selectedJob?.id === job.id ? 'border-accent-border bg-accent-bg' : 'border-border-default bg-surface-1'
              }`}
              onClick={() => setSelectedJobId(job.id)}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-xs font-medium">{job.id}</span>
                <StatusPill label={job.status} tone={statusTone(job.status)} />
              </div>
              <p className="mt-1 truncate text-xs text-text-secondary">
                {job.model_plugin ?? t.jobs.unknownPlugin}
                {job.external_id ? ` · ${job.external_id}` : ''}
              </p>
            </Button>
          ))}
        </div>
      )}

      <Sheet open={Boolean(selectedJob)} onOpenChange={(open) => !open && setSelectedJobId(null)}>
        {selectedJob ? (
          <SheetContent side="right" className="sm:max-w-lg">
            <SheetHeader>
              <SheetTitle>{selectedJob.id}</SheetTitle>
              <SheetDescription>
                {selectedJob.model_plugin ?? t.jobs.unknownPlugin}
              </SheetDescription>
            </SheetHeader>
            <ScrollArea className="min-h-0 flex-1 px-4">
              <div className="space-y-4 pb-4">
                {/* Controlled: the log step resolves after the drawer mounts, and
                    defaultValue is only read once, so the step stayed incomplete for
                    every job whose logs arrived asynchronously - which is all of them. */}
                <Timeline value={logPayload?.logs || selectedJob.error_message ? 2 : 1}>
                  <TimelineItem step={1}>
                    <TimelineIndicator />
                    <TimelineSeparator />
                    <TimelineTitle>
                      <StatusPill
                        label={selectedJob.status}
                        tone={statusTone(selectedJob.status)}
                      />
                    </TimelineTitle>
                    <TimelineContent>
                      {selectedJob.external_id
                        ? format(t.jobs.logQueued, {
                            externalId: selectedJob.external_id,
                            status: selectedJob.status,
                          })
                        : t.jobs.logNoExternalId}
                    </TimelineContent>
                  </TimelineItem>
                  <TimelineItem step={2}>
                    <TimelineIndicator />
                    <TimelineTitle>
                      <span className="inline-flex items-center gap-1">
                        <Terminal className="h-3.5 w-3.5" />
                        {t.jobs.logTail}
                      </span>
                    </TimelineTitle>
                    <TimelineContent>
                      <pre className="max-h-72 overflow-auto rounded-md border border-border-soft bg-foreground/10 p-2 text-xs leading-relaxed text-text-secondary">
                        {logPayload?.logs || selectedJob.error_message || t.jobs.logNoExternalId}
                      </pre>
                    </TimelineContent>
                  </TimelineItem>
                </Timeline>
                <ModelResultGuide pluginKey={selectedJob.model_plugin} />
                <div className="flex flex-wrap gap-2">
                  {isCancellableJob(selectedJob.status) ? (
                    <Button type="button"
                      variant="outline"
                      size="sm"
                      disabled={readOnly || cancel.isPending}
                      onClick={() => cancel.mutate(selectedJob)}
                    >
                      <StopCircle className="h-3.5 w-3.5" />
                      {t.jobs.cancel}
                    </Button>
                  ) : null}
                  {isRetryableJob(selectedJob.status) ? (
                    <Button type="button"
                      variant="outline"
                      size="sm"
                      disabled={readOnly || retry.isPending}
                      onClick={() => retry.mutate(selectedJob)}
                      title={t.jobs.retryTitle}
                    >
                      <ArrowsClockwise className="h-3.5 w-3.5" />
                      {t.jobs.retry}
                    </Button>
                  ) : null}
                  <AttachToGoalButton
                    projectId={selectedJob.project_id}
                    resourceType="job"
                    resourceId={selectedJob.id}
                  />
                  {/* Offered where the run is, and only once it has settled: a decision
                      about a job that is still running is a plan, and the ids that make
                      the record checkable are already on screen here. A finished run is
                      the moment the judgement actually gets made. */}
                  {isSettledJob(selectedJob.status) ? (
                    <RecordDecisionButton
                      projectId={selectedJob.project_id}
                      seed={{
                        lane: 'dry',
                        summary: format(t.jobs.decisionSeedSummary, {
                          plugin: selectedJob.model_plugin ?? t.jobs.unknownPlugin,
                          status: selectedJob.status,
                        }),
                        provenance: {
                          job_ids: [selectedJob.id],
                          // The external id is the cluster's, not ours: it belongs under
                          // the one key that exists for things the platform does not own.
                          external_refs: selectedJob.external_id ? [selectedJob.external_id] : [],
                        },
                      }}
                    />
                  ) : null}
                  {selectedJob.external_id ? (
                    <Button type="button"
                      variant="outline"
                      size="sm"
                      disabled={readOnly || syncResult.isPending}
                      onClick={() => syncResult.mutate(selectedJob)}
                      title={t.jobs.syncResultTitle}
                    >
                      <Download className="h-3.5 w-3.5" />
                      {syncResult.isPending ? t.jobs.syncing : t.jobs.syncResult}
                    </Button>
                  ) : null}
                </div>
              </div>
            </ScrollArea>
          </SheetContent>
        ) : null}
      </Sheet>
      </FramePanel>
    </Frame>
  )
}
