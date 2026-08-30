import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowsClockwise, Download, StopCircle, Terminal } from '@phosphor-icons/react'
import { cancelJob, getJobLogs, listWorkflowJobs, retryJob, syncJobResult } from '../../lib/api/jobs'
import { submitWorkflowNode } from '../../lib/api/workflow'
import { AttachToGoalButton } from '../research/AttachToGoalButton'
import { useJobEventStream } from './useJobEventStream'
import type { Job } from '../../lib/schemas/job'
import { isCancellableJob, isRetryableJob } from '../../lib/schemas/workflow'
import { StatusPill } from '../../components/ui/StatusPill'
import { statusTone } from '../../components/ui/statusTone'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import { DEFAULT_GPU_QUEUE } from '../../lib/config/cluster'
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
import { Input } from '../../components/ui/Input'
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
  overrideParams?: Record<string, unknown>
  /**
   * Hides manual submission. This drawer reaches the compute cluster, so a run the
   * server considers finished - or a demo session, or an unready target - must not be
   * able to start work from here.
   */
  readOnly?: boolean
}

export function JobStatusDrawer({ workflowRunId, readOnly = false, selectedNodeId, overrideParams }: JobStatusDrawerProps) {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [manualOpen, setManualOpen] = useState(false)
  const [queueName, setQueueName] = useState(DEFAULT_GPU_QUEUE)
  const [cpuCount, setCpuCount] = useState(8)
  const [resourceRequirement, setResourceRequirement] = useState('span[ptile=1]')
  const [gpuRequirement, setGpuRequirement] = useState('num=1')
  const queryClient = useQueryClient()
  const showToast = useToastStore((s) => s.show)
  const { t, format } = useI18n()

  const { data: jobs = [] } = useQuery({
    queryKey: ['workflow-jobs', workflowRunId],
    queryFn: () => listWorkflowJobs(workflowRunId!),
    enabled: Boolean(workflowRunId),
    refetchInterval: (query) => {
      const data = query.state.data ?? []
      // Anything not terminal is still moving. The previous list named 'staging' and
      // 'collecting_outputs', which no longer exist, and omitted 'pending', 'dispatching'
      // and 'collecting' - so the list stopped refreshing exactly while work was starting.
      return data.some((job) => isCancellableJob(job.status)) ? 3000 : false
    },
  })

  const visibleJobs = useMemo(() => {
    if (!selectedNodeId) return jobs
    return jobs.filter((job) => job.workflow_node_id === selectedNodeId)
  }, [jobs, selectedNodeId])

  const selectedJob = visibleJobs.find((job) => job.id === selectedJobId) ?? null

  // The job's own event stream, which nothing consumed until now. Polling below is
  // still the floor; this only shortens the gap between a state change and seeing it.
  useJobEventStream(selectedJob && isCancellableJob(selectedJob.status) ? selectedJob.id : null, workflowRunId)

  const { data: logPayload } = useQuery({
    queryKey: ['job-logs', selectedJob?.id],
    queryFn: () => getJobLogs(selectedJob!.id),
    enabled: Boolean(selectedJob?.id),
    refetchInterval: selectedJob && isCancellableJob(selectedJob.status) ? 3000 : false,
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

  const submitManual = useMutation({
    mutationFn: () => {
      if (readOnly) throw new Error(t.workflowExt.canvas.readOnlyBanner)
      if (!selectedNodeId || !workflowRunId) throw new Error(t.jobs.errorSelectNode)
      return submitWorkflowNode(workflowRunId, { override_params: overrideParams })
    },
    onSuccess: async (result) => {
      showToast(format(t.jobs.submitted, { jobId: result.job?.id ?? 'pending' }), 'success')
      await queryClient.invalidateQueries({ queryKey: ['workflow-jobs', workflowRunId] })
    },
    onError: (error) => showToast(error instanceof Error ? error.message : t.jobs.manualSubmitFailed, 'error'),
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
        {!selectedNodeId ? (
          <p className="text-xs leading-relaxed text-text-secondary">{t.jobs.manualSubmitHint}</p>
        ) : (
          <>
            <Button type="button"
              variant="ghost"
              size="sm"
              className="w-full justify-between"
              disabled={readOnly}
              onClick={() => setManualOpen((value) => !value)}
            >
              <span>{t.jobs.manualSubmit}</span>
              <span className="text-text-secondary">{manualOpen ? t.jobs.hide : t.jobs.editQueue}</span>
            </Button>
            {manualOpen ? (
              <div className="mt-3 grid gap-2">
                <label className="grid gap-1 text-[11px] text-text-secondary">
                  {t.jobs.queue}
                  <Input
                    className="rounded border border-border-soft bg-bg-app px-2 py-1.5 text-xs text-text-primary"
                    value={queueName}
                    disabled={readOnly}
                    onChange={(event) => setQueueName(event.target.value)}
                    placeholder={DEFAULT_GPU_QUEUE}
                  />
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="grid gap-1 text-[11px] text-text-secondary">
                    {t.jobs.cpuTasks}
                    <Input
                      className="rounded border border-border-soft bg-bg-app px-2 py-1.5 text-xs text-text-primary"
                      type="number"
                      min={1}
                      max={256}
                      value={cpuCount}
                      disabled={readOnly}
                      onChange={(event) => setCpuCount(Number(event.target.value) || 1)}
                    />
                  </label>
                  <label className="grid gap-1 text-[11px] text-text-secondary">
                    {t.jobs.gpu}
                    <Input
                      className="rounded border border-border-soft bg-bg-app px-2 py-1.5 text-xs text-text-primary"
                      value={gpuRequirement}
                      disabled={readOnly}
                      onChange={(event) => setGpuRequirement(event.target.value)}
                    />
                  </label>
                </div>
                <label className="grid gap-1 text-[11px] text-text-secondary">
                  {t.jobs.resourceRequirement}
                  <Input
                    className="rounded border border-border-soft bg-bg-app px-2 py-1.5 text-xs text-text-primary"
                    value={resourceRequirement}
                    disabled={readOnly}
                    onChange={(event) => setResourceRequirement(event.target.value)}
                  />
                </label>
                <p className="text-[11px] leading-relaxed text-text-secondary">{t.jobs.manualSubmitBody}</p>
                <Button type="button"
                  disabled={readOnly || submitManual.isPending || !queueName.trim()}
                  onClick={() => submitManual.mutate()}
                >
                  {submitManual.isPending ? t.jobs.submitting : t.jobs.submitSelectedNode}
                </Button>
              </div>
            ) : null}
          </>
        )}
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
