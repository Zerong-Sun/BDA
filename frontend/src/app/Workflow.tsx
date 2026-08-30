import { useEffect, useMemo, useRef, useState } from 'react'
import { TargetIdentityFix } from '../features/workflow/TargetIdentityFix'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkle, SpinnerGap } from '@phosphor-icons/react'
import { Link } from 'react-router'
import { WorkflowCanvas, type WorkflowCanvasHandle } from '../features/workflow/WorkflowCanvas'
import { NodeBuilder } from '../features/workflow/NodeBuilder'
import { mapApiGraphToGraph } from '../features/workflow/workflowMapper'
import { WorkflowResourceSidebar } from '../features/workflow/WorkflowResourceSidebar'
import { RunLineage } from '../features/workflow/RunLineage'
import { WorkflowInspector } from '../features/workflow/WorkflowInspector'
import { WorkflowContextBar } from '../features/workflow/WorkflowContextBar'
import { WorkflowToolbar } from '../features/workflow/WorkflowToolbar'
import {
  defaultWorkflowEdges,
  defaultWorkflowNodes,
  type NodeTemplate,
} from '../features/workflow/workflowTypes'
import { ApiState } from '../components/ui/ApiState'
import { NextStep } from '../components/ui/NextStep'
import { getCurrentWorkflowRunOrNull, listProjectWorkflowRuns } from '../lib/api/projects'
import {
  createWorkflowRun,
  getWorkflowGraph,
  getWorkflowPreflight,
  preflightBlockersFrom,
  submitWorkflowRun,
} from '../lib/api/workflow'
import { isTerminalWorkflowRun } from '../lib/schemas/workflow'
import { applyRoutePlan, planRoute, type RoutePlan } from '../lib/api/copilot'
import { listProjectArtifacts } from '../lib/api/artifacts'
import { listModelPlugins, validateModelPlugin } from '../lib/api/registry'
import { awaitOperation } from '../lib/api/operations'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useTargetReadiness } from '../lib/hooks/useProjectTargetStructure'
import { useAppStore } from '../lib/store/appStore'
import { useToastStore } from '../components/ui/toastStore'
import { useI18n } from '../lib/i18n'
import { projectText } from '../lib/i18n/projectText'
import type { Artifact } from '../lib/schemas/artifact'
import type { ModelPlugin } from '../lib/schemas/registry'
import type { TranslationDict } from '../lib/i18n/types'
import { Alert, AlertDescription, AlertTitle } from '../components/reui/alert'
import {
  Frame,
  FrameDescription,
  FrameHeader,
  FramePanel,
  FrameTitle,
} from '../components/reui/frame'
import { Button } from '../components/ui/Button'
import { Checkbox } from '../components/ui/checkbox'
import { Textarea } from '../components/ui/textarea'
import { Skeleton } from '../components/ui/Skeleton'
import { currentRole } from '../features/research/jsonHelpers'

function templateForPlugin(
  plugin: ModelPlugin,
  modelPluginFallback: string,
  format: (template: string, vars: Record<string, string | number | undefined | null>) => string,
): NodeTemplate {
  const pluginType = plugin.plugin_key
  return {
    id: plugin.id,
    icon: plugin.name === 'RFdiffusion' ? 'wand-sparkles' : 'activity',
    title: plugin.name,
    body: format(modelPluginFallback, { modelType: pluginType }),
    resource: pluginType.includes('manual')
      ? 'manual'
      : pluginType.includes('gpu')
        ? 'gpu'
        : 'cpu',
    nodeType: pluginType,
    modelName: plugin.name,
    modelVersion: plugin.plugin_version,
    pluginId: plugin.id,
    parameterSchema: plugin.parameter_schema,
  }
}

function projectObjective(
  project:
    { name?: string; project_type?: string; summary?: string | null } | null | undefined,
  routePlanner: TranslationDict['workflowExt']['routePlanner'],
  format: (template: string, vars: Record<string, string | number | undefined | null>) => string,
) {
  if (!project) return routePlanner.defaultObjective
  if (project.summary?.trim()) return project.summary.trim()
  const type = project.project_type?.replace(/_/g, ' ') ?? 'protein design'
  return format(routePlanner.objectiveForProject, { type, projectName: project.name ?? '' })
}

function routeTarget(
  project: { name?: string; summary?: string | null } | null | undefined,
  objective: string,
) {
  const target =
    project?.name?.trim() || objective.trim().split(/[.;\n]/)[0] || 'protein design target'
  return target.slice(0, 200)
}

const statusLegendKeys = [
  ['notStarted', 'border-border-soft'],
  ['queued', 'border-accent-2/50'],
  ['running', 'border-info'],
  ['completed', 'border-success/50'],
  ['failed', 'border-danger/50'],
] as const

/**
 * The planner only fills a parameter when the registered plugin schema declares
 * it, so showing what landed — and saying plainly when nothing did — is the
 * difference between "the methods defaults are applied" and a silent empty set.
 */
function RouteModuleDefaults({ parameters }: { parameters?: Record<string, unknown> }) {
  const { t } = useI18n()
  const entries = Object.entries(parameters ?? {})
  if (entries.length === 0) {
    return (
      <span className="mt-1 block text-xs text-text-muted">
        {t.workflowExt.routePlanner.moduleNoDefaults}
      </span>
    )
  }
  return (
    <span className="mt-2 block">
      <span className="block text-[10px] uppercase tracking-wide text-accent">
        {t.workflowExt.routePlanner.moduleDefaults}
      </span>
      <span className="mt-1 flex flex-wrap gap-1">
        {entries.map(([name, value]) => (
          <code key={name} className="rounded bg-surface-2 px-1 text-[11px] text-text-secondary">
            {name}={String(value)}
          </code>
        ))}
      </span>
    </span>
  )
}

/** Flattens one level so `tier_a.pae_interaction` reads as a single row. */
function flattenConstraints(constraints: Record<string, unknown>, prefix = ''): [string, string][] {
  return Object.entries(constraints).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return flattenConstraints(value as Record<string, unknown>, path)
    }
    return [[path, Array.isArray(value) ? value.join('–') : String(value)] as [string, string]]
  })
}

function RouteConstraints({ constraints }: { constraints: Record<string, unknown> }) {
  const { t } = useI18n()
  const rows = flattenConstraints(constraints)
  if (rows.length === 0) return null
  return (
    <div className="text-xs text-text-secondary">
      <p className="mb-1 uppercase tracking-wide text-accent">
        {t.workflowExt.routePlanner.routeConstraints}
      </p>
      <div className="flex flex-wrap gap-1">
        {rows.map(([path, value]) => (
          <code key={path} className="rounded bg-surface-2 px-1 text-[11px]">
            {path} {value}
          </code>
        ))}
      </div>
    </div>
  )
}

function WorkflowLegend({ advanced }: { advanced: boolean }) {
  const { t } = useI18n()
  const nodeLegend = [
    [t.workflowExt.legend.targetInputs, t.workflowExt.legend.targetInputsHint],
    [t.workflowExt.legend.generation, t.workflowExt.legend.generationHint],
    [t.workflowExt.legend.prediction, t.workflowExt.legend.predictionHint],
    [t.workflowExt.legend.scoringFilters, t.workflowExt.legend.scoringFiltersHint],
    [t.workflowExt.legend.validation, t.workflowExt.legend.validationHint],
  ] as const

  if (!advanced) {
    return (
      <Frame variant="inverse" spacing="xs" className="mb-4">
        <FramePanel className="text-xs text-text-secondary">
          {t.workflowExt.legend.guidedBody.split(t.workflowExt.legend.advancedLabel)[0]}
          <span className="text-text-primary">{t.workflowExt.legend.advancedLabel}</span>
          {t.workflowExt.legend.guidedBody.split(t.workflowExt.legend.advancedLabel)[1]}
        </FramePanel>
      </Frame>
    )
  }
  return (
    <Frame variant="inverse" spacing="xs" className="mb-4">
      <FramePanel className="grid gap-3 text-xs text-text-secondary xl:grid-cols-[minmax(0,1fr)_auto]">
      <section>
        <p className="mb-2 uppercase tracking-wide text-accent">{t.workflowExt.legend.nodeTypes}</p>
        <div className="flex flex-wrap gap-2">
          {nodeLegend.map(([label, body]) => (
            <span
              key={label}
              className="rounded-md border border-border-soft bg-bg-app px-2 py-1"
              title={body}
            >
              {label}
            </span>
          ))}
        </div>
      </section>
      <section>
        <p className="mb-2 uppercase tracking-wide text-accent">
          {t.workflowExt.legend.statusColors}
        </p>
        <div className="flex flex-wrap gap-2">
          {statusLegendKeys.map(([labelKey, borderClass]) => (
            <span key={labelKey} className="inline-flex items-center gap-1.5">
              <span className={`h-3 w-3 rounded-full border ${borderClass}`} />
              {t.shared.status[labelKey]}
            </span>
          ))}
        </div>
      </section>
      </FramePanel>
    </Frame>
  )
}

export function WorkflowPage() {
  const { projectId, activeProject } = useProjectContext()
  const workflowSeed = useAppStore((s) => s.workflowSeed)
  const setWorkflowSeed = useAppStore((s) => s.setWorkflowSeed)
  const [builderOpen, setBuilderOpen] = useState(false)
  const [goal, setGoal] = useState(() =>
    workflowSeed?.projectId === projectId && workflowSeed.goal.trim() ? workflowSeed.goal : '',
  )
  const [routePlan, setRoutePlan] = useState<RoutePlan | null>(null)
  const [selectedRouteId, setSelectedRouteId] = useState<string>('')
  const [selectedWorkflowRunId, setSelectedWorkflowRunId] = useState<string | null>(null)
  const [selectedModuleIds, setSelectedModuleIds] = useState<string[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | undefined>()
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const canvasRef = useRef<WorkflowCanvasHandle>(null)
  const { t, format, language } = useI18n()
  const appMode = useAppStore((s) => s.appMode)
  const uiDensity = useAppStore((s) => s.uiDensity)
  const showToast = useToastStore((s) => s.show)
  const queryClient = useQueryClient()
  const isDemoMode = appMode === 'demo'
  const routeObjective =
    goal.trim() || projectObjective(activeProject, t.workflowExt.routePlanner, format)
  const targetReadiness = useTargetReadiness(projectId)

  useEffect(() => {
    const resetSelection = window.setTimeout(() => setSelectedWorkflowRunId(null), 0)
    return () => window.clearTimeout(resetSelection)
  }, [projectId])

  useEffect(() => {
    if (workflowSeed?.projectId === projectId && workflowSeed.goal.trim()) {
      const applySeed = window.setTimeout(() => {
        setGoal(workflowSeed.goal)
        setWorkflowSeed(null)
      }, 0)
      return () => window.clearTimeout(applySeed)
    }
  }, [projectId, setWorkflowSeed, workflowSeed])
  const {
    data: currentWorkflowRun,
    isLoading: currentWorkflowLoading,
    isError: workflowError,
    error: workflowQueryError,
    refetch: refetchWorkflow,
  } = useQuery({
    queryKey: ['workflow-run', 'current', projectId],
    queryFn: () => getCurrentWorkflowRunOrNull(projectId),
    enabled: Boolean(projectId),
  })

  const { data: projectWorkflowRuns = [] } = useQuery({
    queryKey: ['workflow-runs', projectId],
    queryFn: () => listProjectWorkflowRuns(projectId),
    enabled: Boolean(projectId),
  })

  const workflowRunId = selectedWorkflowRunId ?? currentWorkflowRun?.id

  const {
    data: workflowGraph,
    isLoading: workflowGraphLoading,
    isError: workflowGraphError,
    error: workflowGraphQueryError,
    refetch: refetchWorkflowGraph,
  } = useQuery({
    queryKey: ['workflow-graph', workflowRunId],
    queryFn: () => getWorkflowGraph(workflowRunId!),
    enabled: Boolean(workflowRunId),
    refetchInterval: (query) => {
      const nodes = query.state.data?.nodes ?? []
      return nodes.some((node) =>
        ['queued', 'staging', 'running', 'collecting_outputs'].includes(node.status),
      )
        ? 3000
        : false
    },
  })

  const workflowPreflight = useQuery({
    queryKey: ['workflow-preflight', workflowRunId],
    queryFn: () => getWorkflowPreflight(workflowRunId!),
    enabled: Boolean(workflowRunId) && !isDemoMode,
  })

  const { data: modelPlugins = [] } = useQuery({
    queryKey: ['model-plugins'],
    queryFn: listModelPlugins,
    enabled: Boolean(workflowRunId) && !isDemoMode,
  })

  const validatePlugin = useMutation({
    mutationFn: async (pluginId: string) => {
      const accepted = await validateModelPlugin(pluginId)
      return awaitOperation(accepted.operation_id)
    },
    onSuccess: async () => {
      showToast(t.workflowExt.routePlanner.pluginValidationComplete, 'success')
      await queryClient.invalidateQueries({ queryKey: ['model-plugins'] })
      await queryClient.invalidateQueries({ queryKey: ['workflow-preflight', workflowRunId] })
    },
    onError: (error) =>
      showToast(
        error instanceof Error
          ? `${t.workflowExt.routePlanner.pluginValidationFailed} ${error.message}`
          : t.workflowExt.routePlanner.pluginValidationFailed,
        'error',
      ),
  })

  const { data: projectArtifacts = [] } = useQuery({
    queryKey: ['project-artifacts', projectId],
    queryFn: () => listProjectArtifacts(projectId),
    enabled: Boolean(projectId),
  })

  const workflowNodes = useMemo(() => workflowGraph?.nodes ?? [], [workflowGraph?.nodes])
  const workflowPluginIds = useMemo(
    () => new Set(workflowNodes.map((node) => node.model_plugin_id).filter(Boolean)),
    [workflowNodes],
  )
  const visibleArtifacts = useMemo(() => {
    const byId = new Map<string, Artifact>()
    for (const artifact of [...projectArtifacts, ...artifacts]) {
      byId.set(artifact.id, artifact)
    }
    return Array.from(byId.values())
  }, [artifacts, projectArtifacts])

  const graph = useMemo(
    () =>
      workflowNodes.length > 0
        ? mapApiGraphToGraph(workflowNodes, workflowGraph?.edges ?? [])
        : null,
    [workflowGraph?.edges, workflowNodes],
  )
  const selectedNode = workflowNodes.find((node) => node.id === selectedNodeId) ?? null
  const selectedArtifact =
    visibleArtifacts.find((artifact) => artifact.id === selectedArtifactId) ?? null

  const workflowRun = workflowGraph?.workflow ?? currentWorkflowRun
  const targetReady = targetReadiness.data?.ready_for_workflow === true
  const readOnly = isDemoMode || !targetReady || isTerminalWorkflowRun(workflowRun?.status)
  const showRoutePlanner =
    !isDemoMode &&
    targetReady &&
    (!workflowRunId || workflowNodes.length === 0 || Boolean(goal.trim()))
  const routeTargetLabel = routeTarget(activeProject, routeObjective)

  const selectedRoute =
    routePlan?.route_options.find((route) => route.route_id === selectedRouteId) ?? null

  const createWorkflow = useMutation({
    mutationFn: () => createWorkflowRun(projectId),
    onSuccess: (run) => {
      setSelectedWorkflowRunId(run.id)
      queryClient.invalidateQueries({ queryKey: ['workflow-graph', run.id] })
      queryClient.invalidateQueries({ queryKey: ['workflow-preflight', run.id] })
      queryClient.invalidateQueries({ queryKey: ['workflow-run', 'current', projectId] })
      showToast(t.workflowExt.toasts.runCreated, 'success')
    },
    onError: () => showToast(t.workflowExt.toasts.runCreateFailed, 'error'),
  })

  const generatePlan = useMutation({
    mutationFn: () =>
      planRoute({
        project_id: projectId,
        target: routeTargetLabel,
        objective: routeObjective,
      }),
    onSuccess: (plan) => {
      const recommended =
        plan.route_options.find((route) => route.recommended) ?? plan.route_options[0]
      setRoutePlan(plan)
      setSelectedRouteId(recommended?.route_id ?? '')
      setSelectedModuleIds(
        recommended?.modules
          .filter((module) => module.available)
          .map((module) => module.module_id) ?? [],
      )
      showToast(t.workflowExt.toasts.routePrepared, 'success')
    },
    onError: (error) =>
      showToast(
        error instanceof Error
          ? format(t.workflowExt.toasts.routePrepareFailedDetail, { message: error.message })
          : t.workflowExt.toasts.routePrepareFailed,
        'error',
      ),
  })

  const applyPlannedRoute = useMutation({
    mutationFn: async () => {
      if (!selectedRoute) throw new Error(t.workflowExt.toasts.selectRouteFirst)
      return applyRoutePlan({
        project_id: projectId,
        route_id: selectedRoute.route_id,
        objective: routeObjective,
        target: routePlan?.target ?? routeTargetLabel,
        selected_module_ids: selectedModuleIds,
        module_parameters: Object.fromEntries(
          selectedRoute.modules
            .filter((module) => selectedModuleIds.includes(module.module_id))
            .map((module) => [module.module_id, module.default_parameters ?? {}]),
        ),
      })
    },
    onSuccess: (result) => {
      const runId = String(result.workflow_run.id)
      setSelectedWorkflowRunId(runId)
      showToast(t.workflowExt.toasts.routeCreated, 'success')
      queryClient.invalidateQueries({ queryKey: ['workflow-runs', projectId] })
      queryClient.invalidateQueries({ queryKey: ['workflow-run', 'current', projectId] })
      queryClient.invalidateQueries({ queryKey: ['workflow-graph', runId] })
      queryClient.invalidateQueries({ queryKey: ['workflow-preflight', runId] })
    },
    onError: () => showToast(t.workflowExt.toasts.routeCreateFailed, 'error'),
  })

  const startWorkflow = useMutation({
    mutationFn: () => {
      if (!workflowRunId) {
        throw new Error(t.workflowExt.toasts.noWorkflowRun)
      }
      return submitWorkflowRun(workflowRunId)
    },
    onSuccess: () => {
      showToast(t.workflowExt.toasts.submitted, 'success')
      queryClient.invalidateQueries({ queryKey: ['workflow-graph', workflowRunId] })
      queryClient.invalidateQueries({ queryKey: ['workflow-preflight', workflowRunId] })
      queryClient.invalidateQueries({ queryKey: ['workflow-jobs', workflowRunId] })
    },
    onError: (error) => {
      const blockers = preflightBlockersFrom(error)
      if (blockers.length > 0) {
        showToast(`${t.workflowExt.toasts.computeBlocked} ${blockers.join('; ')}`, 'info')
        queryClient.invalidateQueries({ queryKey: ['workflow-preflight', workflowRunId] })
        return
      }
      showToast(t.workflowExt.toasts.startFailed, 'error')
    },
  })

  const addPluginNode = async (plugin: ModelPlugin) => {
    if (!workflowRunId || readOnly) return
    try {
      await canvasRef.current?.addNodeFromTemplate(
        templateForPlugin(plugin, t.nodeBuilder.modelPluginFallback, format),
        plugin.name,
        [],
        {},
      )
      showToast(
        format(t.workflowExt.toasts.pluginAdded, { modelName: plugin.name }),
        'success',
      )
      queryClient.invalidateQueries({ queryKey: ['workflow-graph', workflowRunId] })
    } catch (error) {
      showToast(
        error instanceof Error ? error.message : t.workflowExt.toasts.addPluginFailed,
        'error',
      )
    }
  }

  return (
    <Frame
      variant="inverse"
      spacing="xs"
      className="bg-transparent"
      data-tour-id="workflow-page"
    >
      <WorkflowContextBar
        workflowRunId={workflowRunId}
        workflowStatus={workflowRun?.status}
        projectWorkflowRuns={projectWorkflowRuns}
        onSelectRun={(runId) => {
          setSelectedWorkflowRunId(runId)
          setSelectedNodeId(null)
          setSelectedArtifactId(undefined)
        }}
      />

      {!isDemoMode && targetReadiness.isSuccess && !targetReady ? (
        <Alert className="mb-4" variant="warning">
          <AlertTitle>
            {t.workflowExt.routePlanner.targetBlockedTitle}
          </AlertTitle>
          <AlertDescription>
          <p>
            {targetReadiness.data.next_action || t.workflowExt.routePlanner.targetBlockedBody}
          </p>
          {targetReadiness.data.blockers.length > 0 ? (
            <ul className="mt-2 list-disc pl-5">
              {targetReadiness.data.blockers.map((blocker) => (
                <li key={blocker}>{blocker}</li>
              ))}
            </ul>
          ) : null}
          {/* The structure flow can only help a protein that needs coordinates. When the
              blocker is identity, offer the fix inline - a small-molecule target has no
              structure to prepare and would be sent in a circle by that link. */}
          {targetReadiness.data.blockers.includes('target_identity_unconfirmed') ? (
            <TargetIdentityFix
              projectId={projectId}
              defaultName={activeProject ? projectText(activeProject, 'name', language) : undefined}
            />
          ) : (
            <Button
              className="mt-3"
              render={
                <Link
                  to={`/research?tab=structures&project=${encodeURIComponent(projectId)}`}
                />
              }
            >
              {t.workflowExt.routePlanner.resolveTarget}
            </Button>
          )}
          </AlertDescription>
        </Alert>
      ) : null}

      {!isDemoMode && targetReadiness.isError ? (
        <Alert className="mb-4" variant="destructive">
          <AlertTitle>{t.workflowExt.routePlanner.readinessUnavailableTitle}</AlertTitle>
          <AlertDescription>{t.workflowExt.routePlanner.readinessUnavailableBody}</AlertDescription>
        </Alert>
      ) : null}

      <WorkflowToolbar
        isDemoMode={isDemoMode}
        readOnly={readOnly}
        workflowRunId={workflowRunId}
        createPending={createWorkflow.isPending}
        startPending={startWorkflow.isPending}
        submitDisabled={readOnly || workflowPreflight.data?.allowed !== true}
        onCreateRun={() => createWorkflow.mutate()}
        onNewRoute={() => createWorkflow.mutate()}
        onAddNode={() => setBuilderOpen((v) => !v)}
        onStart={() => startWorkflow.mutate()}
      />

      {!isDemoMode && workflowRun?.derived_from_id ? (
        <Frame variant="inverse" spacing="sm" className="mb-4">
          <FramePanel>
            <RunLineage run={workflowRun} />
          </FramePanel>
        </Frame>
      ) : null}

      {!isDemoMode && targetReady && workflowRunId && workflowPreflight.data ? (
        <Alert
          className="mb-4"
          variant={workflowPreflight.data.allowed ? 'success' : 'warning'}
        >
          <AlertTitle>
            {workflowPreflight.data.allowed
              ? t.workflowExt.routePlanner.preflightReadyTitle
              : t.workflowExt.routePlanner.preflightBlockedTitle}
          </AlertTitle>
          <AlertDescription>
          {workflowPreflight.data.blockers.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {workflowPreflight.data.blockers.map((blocker, index) => (
                <li key={`${blocker.code}-${blocker.node_key ?? blocker.port ?? index}`}>
                  {blocker.node_key ? `${blocker.node_key}: ` : ''}
                  {blocker.message}
                </li>
              ))}
            </ul>
          ) : null}
          {/* Keyed on plugin too: plugin-level warnings share a code, one per plugin. */}
          {workflowPreflight.data.warnings.map((warning, index) => {
            const plugin =
              modelPlugins.find((item) => item.id === warning.plugin_id) ??
              modelPlugins.find(
                (item) =>
                  item.plugin_key === warning.plugin_key && workflowPluginIds.has(item.id),
              )
            const canValidate =
              warning.code === 'plugin_unvalidated' &&
              currentRole() === 'admin' &&
              Boolean(plugin)
            const pending = validatePlugin.isPending && validatePlugin.variables === plugin?.id
            return (
              <div
                key={`${warning.code}-${warning.plugin_id ?? warning.plugin_key ?? warning.node_key ?? index}`}
                className="mt-2 flex flex-wrap items-center gap-2 text-text-muted"
              >
                <span>{warning.message}</span>
                {canValidate ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="xs"
                    disabled={validatePlugin.isPending}
                    onClick={() => plugin && validatePlugin.mutate(plugin.id)}
                  >
                    {pending ? <SpinnerGap className="h-3.5 w-3.5 animate-spin" /> : null}
                    {pending
                      ? t.workflowExt.routePlanner.validatingPlugin
                      : t.workflowExt.routePlanner.validatePlugin}
                  </Button>
                ) : null}
              </div>
            )
          })}
          </AlertDescription>
        </Alert>
      ) : null}

      <ApiState
        isError={workflowError || workflowGraphError}
        error={workflowQueryError ?? workflowGraphQueryError}
        onRetry={() => {
          void refetchWorkflow()
          void refetchWorkflowGraph()
        }}
      >
        {showRoutePlanner ? (
          <Frame variant="inverse" spacing="sm" className="mb-4">
            <FrameHeader>
              <FrameTitle>{t.workflowExt.routePlanner.label}</FrameTitle>
              <FrameDescription>{t.workflowExt.routePlanner.emptyHint}</FrameDescription>
            </FrameHeader>
            <FramePanel>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
              <div className="min-w-0 flex-1">
                <label
                  htmlFor="workflow-goal"
                  className="mb-1 block text-xs uppercase tracking-wide text-accent"
                >
                  {t.workflowExt.routePlanner.label}
                </label>
                <Textarea
                  id="workflow-goal"
                  rows={2}
                  className="w-full resize-none rounded-md border border-border-soft bg-bg-app px-3 py-2 text-sm text-text-primary"
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  placeholder={projectObjective(activeProject, t.workflowExt.routePlanner, format)}
                />
              </div>
              <Button type="button"
                disabled={generatePlan.isPending || readOnly || !routeObjective.trim()}
                onClick={() => generatePlan.mutate()}
              >
                <Sparkle className="h-4 w-4" />
                {t.workflowExt.routePlanner.planRoutes}
              </Button>
            </div>
            {routePlan ? (
              <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
                <div className="grid gap-3">
                  <div className="flex flex-wrap gap-2">
                    {routePlan.route_options.map((route) => (
                      <Button type="button"
                        key={route.route_id}
                        variant={route.route_id === selectedRouteId ? 'secondary' : 'outline'}
                        className={`h-auto flex-col items-start rounded-md border px-3 py-2 text-left text-sm whitespace-normal ${
                          route.route_id === selectedRouteId
                            ? 'border-accent-border bg-accent-bg text-text-primary'
                            : 'border-border-soft text-text-primary hover:border-accent/50'
                        }`}
                        onClick={() => {
                          setSelectedRouteId(route.route_id)
                          setSelectedModuleIds(
                            route.modules
                              .filter((module) => module.available)
                              .map((module) => module.module_id),
                          )
                        }}
                      >
                        <span className="block font-medium">{route.label}</span>
                        <span className="block text-xs text-text-secondary">
                          {format(t.workflowExt.routePlanner.modules, {
                            count: route.estimated_steps,
                          })}
                        </span>
                      </Button>
                    ))}
                  </div>
                  {selectedRoute ? (
                    <div className="grid gap-3">
                      <div>
                        <p className="text-sm text-text-primary">{selectedRoute.summary}</p>
                        <ul className="mt-2 grid gap-1 text-xs text-text-secondary">
                          {selectedRoute.rationale.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="grid gap-2 sm:grid-cols-2">
                        {selectedRoute.modules.map((module) => (
                          <label
                            key={module.module_id}
                            className={`flex items-start gap-2 rounded-md border border-border-soft bg-bg-app p-3 text-sm ${
                              module.available
                                ? 'text-text-primary'
                                : 'text-text-secondary opacity-70'
                            }`}
                          >
                            <Checkbox
                              className="mt-1"
                              disabled={!module.available}
                              checked={selectedModuleIds.includes(module.module_id)}
                              onCheckedChange={(checked) => {
                                setSelectedModuleIds((current) =>
                                  checked === true
                                    ? [...new Set([...current, module.module_id])]
                                    : current.filter((id) => id !== module.module_id),
                                )
                              }}
                            />
                            <span className="min-w-0">
                              <span className="block font-medium">{module.model_name}</span>
                              <span className="block text-xs text-text-secondary">
                                {module.summary}
                              </span>
                              <RouteModuleDefaults parameters={module.default_parameters} />
                            </span>
                          </label>
                        ))}
                      </div>
                      {selectedRoute.risks.length > 0 ? (
                        <div className="text-xs text-text-secondary">
                          <p className="mb-1 uppercase tracking-wide text-accent">
                            {t.workflowExt.routePlanner.routeRisks}
                          </p>
                          <ul className="ml-4 list-disc">
                            {selectedRoute.risks.map((risk) => (
                              <li key={risk}>{risk}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      <RouteConstraints constraints={selectedRoute.constraints} />
                      <Button type="button"
                        className="w-fit"
                        disabled={
                          readOnly || applyPlannedRoute.isPending || selectedModuleIds.length === 0
                        }
                        onClick={() => applyPlannedRoute.mutate()}
                      >
                        <Sparkle className="h-4 w-4" />
                        {t.workflowExt.routePlanner.createFromRoute}
                      </Button>
                    </div>
                  ) : null}
                </div>
                <aside className="grid gap-3 text-xs text-text-secondary">
                  <div>
                    <p className="mb-1 uppercase tracking-wide text-accent">
                      {t.workflowExt.routePlanner.knowledgeUsed}
                    </p>
                    <ul className="grid gap-1">
                      {routePlan.knowledge_context.map((item) => (
                        <li key={item.knowledge_entry_id}>{item.title}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="mb-1 uppercase tracking-wide text-accent">
                      {t.workflowExt.routePlanner.analysisProcess}
                    </p>
                    <ol className="grid gap-1">
                      {routePlan.analysis_trace.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ol>
                  </div>
                </aside>
              </div>
            ) : (
              <p className="mt-3 text-xs text-text-secondary">
                {t.workflowExt.routePlanner.emptyHint}
              </p>
            )}
            </FramePanel>
          </Frame>
        ) : null}

        {!workflowRunId && !isDemoMode ? (
          <Frame variant="inverse" spacing="sm" className="mb-4 text-center">
            <FrameHeader>
              <FrameTitle className="text-lg text-text-primary">
                {t.workflowExt.routePlanner.createWorkflowTitle}
              </FrameTitle>
            </FrameHeader>
            <FramePanel className="text-sm text-text-secondary">
              <FrameDescription className="mx-auto max-w-2xl">
                {t.workflowExt.routePlanner.createWorkflowBody}
              </FrameDescription>
            </FramePanel>
          </Frame>
        ) : null}

        {uiDensity === 'advanced' ? <WorkflowLegend advanced /> : null}

        <div className="grid min-h-0 gap-4 xl:h-[calc(100vh-12rem)] xl:min-h-[38rem] xl:grid-cols-[300px_minmax(0,1fr)_340px]">
          <div className="order-2 min-h-0 xl:order-1">
            <WorkflowResourceSidebar
              projectId={projectId}
              artifacts={visibleArtifacts}
              selectedNode={selectedNode}
              selectedArtifactId={selectedArtifactId}
              onArtifactUploaded={(artifact) => {
                setArtifacts((current) => [
                  artifact,
                  ...current.filter((item) => item.id !== artifact.id),
                ])
                queryClient.invalidateQueries({ queryKey: ['project-artifacts', projectId] })
                setSelectedArtifactId(artifact.id)
                setSelectedNodeId(null)
              }}
              onArtifactSelected={(artifact) => {
                setSelectedArtifactId(artifact.id)
                setSelectedNodeId(null)
              }}
              onPluginAdd={(plugin) => void addPluginNode(plugin)}
              readOnly={readOnly || !workflowRunId}
            />
          </div>

          <main className="order-1 min-w-0 xl:order-2" data-tour-id="workflow-canvas">
            {currentWorkflowLoading || workflowGraphLoading ? (
              <Frame className="h-full min-h-96" aria-label={t.shared.apiState.loadingDefault}>
                <FramePanel className="grid h-full gap-3 p-4">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-full min-h-80 w-full" />
                </FramePanel>
              </Frame>
            ) : isDemoMode ? (
              <WorkflowCanvas
                initialNodes={defaultWorkflowNodes}
                initialEdges={defaultWorkflowEdges}
                readOnly
                onNodeSelected={setSelectedNodeId}
              />
            ) : workflowRunId ? (
              <>
                <NodeBuilder
                  open={builderOpen && !readOnly}
                  onClose={() => setBuilderOpen(false)}
                  onAdd={async (template, nodeName, methods, parameters) => {
                    try {
                      await canvasRef.current?.addNodeFromTemplate(
                        template,
                        nodeName,
                        methods,
                        parameters,
                      )
                      showToast(format(t.workflowExt.toasts.nodeAdded, { nodeName }), 'success')
                      setBuilderOpen(false)
                      queryClient.invalidateQueries({ queryKey: ['workflow-graph', workflowRunId] })
                      queryClient.invalidateQueries({
                        queryKey: ['workflow-preflight', workflowRunId],
                      })
                    } catch (err) {
                      const message =
                        err instanceof Error ? err.message : t.workflowExt.toasts.addNodeFailed
                      showToast(message, 'error')
                      throw err
                    }
                  }}
                />

                <WorkflowCanvas
                  ref={canvasRef}
                  initialNodes={graph?.nodes ?? []}
                  initialEdges={graph?.edges ?? []}
                  workflowRunId={workflowRunId}
                  readOnly={readOnly}
                  onNodeSelected={(nodeId) => {
                    setSelectedNodeId(nodeId)
                    setSelectedArtifactId(undefined)
                  }}
                  onNodeAdded={() => {
                    queryClient.invalidateQueries({ queryKey: ['workflow-graph', workflowRunId] })
                    queryClient.invalidateQueries({
                      queryKey: ['workflow-preflight', workflowRunId],
                    })
                  }}
                  onLayoutSaved={() => {
                    queryClient.invalidateQueries({ queryKey: ['workflow-graph', workflowRunId] })
                    queryClient.invalidateQueries({
                      queryKey: ['workflow-preflight', workflowRunId],
                    })
                  }}
                />
              </>
            ) : (
              <WorkflowCanvas initialNodes={[]} initialEdges={[]} />
            )}
          </main>

          <div className="order-3 min-h-0" data-tour-id="workflow-inspector">
            <WorkflowInspector
              workflowRunId={workflowRunId}
              readOnly={readOnly}
              selectedNode={selectedNode}
              selectedArtifact={selectedArtifact}
              nodeCount={workflowNodes.length}
              artifactCount={visibleArtifacts.length}
              nodes={workflowNodes}
            />
          </div>
        </div>
      </ApiState>

      {!isDemoMode ? <NextStep stage="workflow" /> : null}
    </Frame>
  )
}
