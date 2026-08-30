import { useMemo, useState, type ReactNode } from 'react'
import { Copy, Download, FileCode, FloppyDisk, Gear, Network, PlugsConnected } from '@phosphor-icons/react'
import type { WorkflowInputBinding, WorkflowNode } from '../../lib/schemas/workflow'
import type { Artifact } from '../../lib/schemas/artifact'
import { formatBytes } from '../../lib/schemas/artifact'
import { downloadArtifact } from '../../lib/api/artifacts'
import { StatusPill } from '../../components/ui/StatusPill'
import { statusTone } from '../../components/ui/statusTone'
import { JobStatusDrawer } from '../jobs'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useToastStore } from '../../components/ui/toastStore'
import { listModelPlugins } from '../../lib/api/registry'
import {
  getWorkflowPreflight,
  previewWorkflowNodeScript,
  updateWorkflowNode,
  type ScriptPreviewResponse,
} from '../../lib/api/workflow'
import { ParameterSchemaForm } from '../plugins'
import { InputBindingPanel } from './InputBindingPanel'
import { listProjectArtifacts } from '../../lib/api/artifacts'
import { defaultsFromFields, fieldsFromParameterSchema } from '../../lib/forms/parameterSchema'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { ClusterDrafts } from '../copilot/ClusterDrafts'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Frame, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { ScrollArea } from '../../components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'

interface WorkflowInspectorProps {
  workflowRunId?: string
  selectedNode?: WorkflowNode | null
  selectedArtifact?: Artifact | null
  nodeCount?: number
  artifactCount?: number
  /** Sibling nodes, so an input can be bound to an upstream node's output port. */
  nodes?: WorkflowNode[]
  /**
   * Editing is refused by the server once a run leaves 'draft', so the inspector has to
   * stop offering it. Without this the panel accepted edits and only surfaced the
   * refusal as a 409 after the user had already done the work.
   */
  readOnly?: boolean
}

export function WorkflowInspector(props: WorkflowInspectorProps) {
  const selectionKey =
    props.selectedNode?.id ?? props.selectedArtifact?.id ?? 'empty'
  return <WorkflowInspectorContent key={selectionKey} {...props} />
}

function WorkflowInspectorContent({
  workflowRunId,
  selectedNode,
  selectedArtifact,
  nodeCount = 0,
  artifactCount = 0,
  nodes = [],
  readOnly = false,
}: WorkflowInspectorProps) {
  const parameters = selectedNode?.parameters ?? {}
  const metrics = typeof selectedNode?.parameters.metrics === 'object' && selectedNode.parameters.metrics
    ? selectedNode.parameters.metrics as Record<string, unknown>
    : {}
  const [draftParameters, setDraftParameters] = useState<Record<string, unknown>>(parameters)
  const [draftBindings, setDraftBindings] = useState<WorkflowInputBinding[]>(
    selectedNode?.input_bindings ?? [],
  )
  const [scriptPreview, setScriptPreview] = useState<ScriptPreviewResponse | null>(null)
  const [queueName, setQueueName] = useState(selectedNode?.queue ?? '')
  const [previewBackend, setPreviewBackend] = useState('lsf')
  const showToast = useToastStore((s) => s.show)
  const queryClient = useQueryClient()
  const { t, language } = useI18n()
  const { projectId } = useProjectContext()
  const hasDownload = Boolean(selectedArtifact?.download_url)

  const { data: modelPlugins = [] } = useQuery({
    queryKey: ['model-plugins'],
    queryFn: listModelPlugins,
  })
  const nodePreflight = useQuery({
    queryKey: ['workflow-preflight', workflowRunId, selectedNode?.id],
    queryFn: () => getWorkflowPreflight(workflowRunId!, selectedNode!.id),
    enabled: Boolean(workflowRunId && selectedNode),
  })

  const { data: projectArtifacts = [] } = useQuery({
    queryKey: ['project-artifacts', projectId],
    queryFn: () => listProjectArtifacts(projectId!),
    enabled: Boolean(projectId),
  })

  // Nodes reference plugins by id when registered, falling back to the display name for
  // nodes created before a plugin was linked.
  const pluginFor = (node?: WorkflowNode | null) =>
    modelPlugins.find((plugin) => plugin.id === node?.model_plugin_id) ??
    modelPlugins.find((plugin) => plugin.name === node?.model_plugin)

  const activePlugin = useMemo(
    () =>
      modelPlugins.find((plugin) => plugin.id === selectedNode?.model_plugin_id) ??
      modelPlugins.find((plugin) => plugin.name === selectedNode?.model_plugin),
    [modelPlugins, selectedNode?.model_plugin, selectedNode?.model_plugin_id],
  )

  const pluginsByNodeKey = useMemo(
    () => Object.fromEntries(nodes.map((item) => [item.node_key, pluginFor(item)])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [nodes, modelPlugins],
  )
  // Resources come from the plugin declaration, not from per-node text boxes: the
  // scheduler directives are rendered from them server-side.
  const resourceSummary = useMemo(() => {
    const resources = (activePlugin?.resources ?? {}) as Record<string, unknown>
    const parts = Object.entries(resources)
      .filter(([, value]) => value !== null && value !== undefined && value !== '')
      .map(([key, value]) => `${key}=${String(value)}`)
    return parts.length ? parts.join(' · ') : t.workflowExt.inspector.resourceFromPlugin
  }, [activePlugin?.resources, t])

  const parameterFields = useMemo(
    () =>
      fieldsFromParameterSchema(
        activePlugin?.parameter_schema,
        selectedNode?.model_plugin ?? undefined,
      ),
    [activePlugin?.parameter_schema, selectedNode?.model_plugin],
  )
  const parameterSchema = useMemo(() => ({ fields: parameterFields }), [parameterFields])
  const effectiveParameters = useMemo(
    () => ({ ...defaultsFromFields(parameterFields), ...draftParameters }),
    [draftParameters, parameterFields],
  )

  const saveParameters = useMutation({
    mutationFn: () => {
      if (readOnly) throw new Error(t.workflowExt.canvas.readOnlyBanner)
      if (!workflowRunId || !selectedNode) throw new Error(t.workflowExt.inspector.errorSelectNode)
      return updateWorkflowNode(workflowRunId, selectedNode.id, {
        parameters: effectiveParameters,
        input_bindings: draftBindings,
        queue: queueName.trim() || null,
      })
    },
    onSuccess: async () => {
      showToast(t.workflowExt.toasts.paramsSaved, 'success')
      await queryClient.invalidateQueries({ queryKey: ['workflow-graph', workflowRunId] })
      await queryClient.invalidateQueries({ queryKey: ['workflow-preflight', workflowRunId] })
    },
    onError: (error) =>
      showToast(
        error instanceof Error ? error.message : t.workflowExt.toasts.paramsSaveFailed,
        'error',
      ),
  })

  const previewScript = useMutation({
    mutationFn: () => {
      if (!selectedNode) throw new Error(t.workflowExt.inspector.errorSelectNode)
      return previewWorkflowNodeScript(selectedNode.id, {
        override_params: effectiveParameters,
        compute_backend: previewBackend,
      })
    },
    onSuccess: (preview) => {
      setScriptPreview(preview)
      showToast(t.workflowExt.toasts.scriptGenerated, 'success')
    },
    onError: (error) =>
      showToast(
        error instanceof Error ? error.message : t.workflowExt.toasts.scriptFailed,
        'error',
      ),
  })

  const downloadSelectedArtifact = async () => {
    if (!selectedArtifact) return
    try {
      await downloadArtifact(selectedArtifact)
    } catch (error) {
      showToast(
        error instanceof Error ? error.message : t.workflowExt.toasts.artifactDownloadFailed,
        'error',
      )
    }
  }

  const downloadScriptPreview = () => {
    if (!scriptPreview || !selectedNode) return
    const blob = new Blob([scriptPreview.script], { type: 'text/x-shellscript' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${selectedNode.node_key.replace(/[^A-Za-z0-9_.-]+/g, '_') || 'workflow_node'}.lsf`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const copyScriptPreview = async () => {
    if (!scriptPreview) return
    await navigator.clipboard.writeText(scriptPreview.script)
    showToast(t.workflowExt.toasts.scriptCopied, 'success')
  }

  return (
    <Frame variant="inverse" spacing="xs" className="h-full min-h-[32rem] w-[340px] shrink-0 2xl:min-h-0">
      <FrameHeader>
        <FrameTitle>
          {selectedNode
            ? t.workflowExt.inspector.nodeInspector
            : selectedArtifact
              ? t.workflowExt.inspector.artifactInspector
              : t.workflowExt.inspector.workflowSummary}
        </FrameTitle>
      </FrameHeader>

      <FramePanel className="min-h-0 overflow-hidden">
      <ScrollArea className="h-full">
      <div className="space-y-3 pr-3">
        {selectedNode ? (
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-semibold">{selectedNode.node_key}</h3>
                <p className="mt-1 text-xs text-text-secondary">
                  {selectedNode.model_plugin ?? selectedNode.node_type}
                </p>
              </div>
              <StatusPill label={selectedNode.status} tone={statusTone(selectedNode.status)} />
            </div>

            <RouteDisplayCatalog
              parameters={selectedNode.parameters}
              language={language}
            />

            <InspectorBlock
              icon={<PlugsConnected className="h-3.5 w-3.5" />}
              title={t.workflowExt.inspector.inputs}
            >
              <InputBindingPanel
                node={selectedNode}
                plugin={activePlugin}
                nodes={nodes}
                pluginsByNodeKey={pluginsByNodeKey}
                artifacts={projectArtifacts}
                bindings={draftBindings}
                onChange={setDraftBindings}
                readOnly={readOnly}
              />
            </InspectorBlock>

            <InspectorBlock
              icon={<Gear className="h-3.5 w-3.5" />}
              title={t.workflowExt.inspector.parameters}
            >
              <ParameterSchemaForm
                schema={parameterSchema}
                values={effectiveParameters}
                onChange={setDraftParameters}
                disabled={readOnly}
              />
              <div className="mt-3 grid gap-2 rounded-md border border-border-soft bg-bg-app p-2">
                <label className="grid gap-1 text-[11px] text-text-secondary">
                  {t.workflowExt.inspector.lsfQueueOverride}
                  <Input
                    className="rounded border border-border-soft bg-surface-1 px-2 py-1.5 text-xs text-text-primary"
                    value={queueName}
                    disabled={readOnly}
                    onChange={(event) => setQueueName(event.target.value)}
                    placeholder={t.workflowExt.inspector.lsfQueuePlaceholder}
                  />
                </label>
                <div className="grid gap-1 text-[11px] text-text-secondary">
                  <span>{t.workflowExt.inspector.previewBackend}</span>
                  <Select
                    value={previewBackend}
                    onValueChange={(value) => setPreviewBackend(value ?? 'lsf')}
                  >
                    <SelectTrigger aria-label={t.workflowExt.inspector.previewBackend} className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="lsf">lsf</SelectItem>
                      <SelectItem value="docker">docker</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1 text-[11px] text-text-secondary">
                  {t.workflowExt.inspector.resource}
                  <p className="rounded border border-border-soft bg-surface-1 px-2 py-1.5 text-xs text-text-primary">
                    {resourceSummary}
                  </p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="button"
                  variant="outline"
                  size="sm"
                  disabled={readOnly || saveParameters.isPending}
                  onClick={() => saveParameters.mutate()}
                >
                  <FloppyDisk className="h-3.5 w-3.5" />
                  {saveParameters.isPending
                    ? t.workflowExt.inspector.saving
                    : t.workflowExt.inspector.saveParameters}
                </Button>
                <Button type="button"
                  size="sm"
                  disabled={previewScript.isPending || nodePreflight.data?.allowed !== true}
                  onClick={() => previewScript.mutate()}
                >
                  <FileCode className="h-3.5 w-3.5" />
                  {previewScript.isPending
                    ? t.workflowExt.inspector.generating
                    : t.workflowExt.inspector.generateScript}
                </Button>
              </div>
              {nodePreflight.data && !nodePreflight.data.allowed ? (
                <Alert className="mt-2" variant="warning">
                  <AlertDescription>
                    {nodePreflight.data.blockers[0]?.message ??
                      t.workflowExt.inspector.scriptPreflightBlocked}
                  </AlertDescription>
                </Alert>
              ) : null}
              {scriptPreview ? (
                <div className="mt-3 rounded-md border border-border-soft bg-bg-app">
                  <div className="flex items-center justify-between gap-2 border-b border-border-soft px-2 py-1.5">
                    <span className="truncate text-xs text-text-secondary">
                      {scriptPreview.plugin_id ?? t.jobs.unknownPlugin} · {scriptPreview.workflow_node_id}
                    </span>
                    <span className="flex gap-1">
                      <Button type="button"
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => void copyScriptPreview()}
                        title={t.workflowExt.inspector.copyScriptTitle}
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </Button>
                      <Button type="button"
                        variant="ghost"
                        size="icon-xs"
                        onClick={downloadScriptPreview}
                        title={t.workflowExt.inspector.downloadScriptTitle}
                      >
                        <Download className="h-3.5 w-3.5" />
                      </Button>
                    </span>
                  </div>
                  <pre className="max-h-80 overflow-auto p-2 text-[11px] leading-relaxed text-text-secondary">
                    {scriptPreview.script}
                  </pre>
                </div>
              ) : null}
            </InspectorBlock>

            <InspectorBlock
              icon={<Network className="h-3.5 w-3.5" />}
              title={t.workflowExt.inspector.metrics}
            >
              <KeyValueGrid data={metrics} empty={t.workflowExt.inspector.noMetrics} />
            </InspectorBlock>

            {selectedNode.error_message ? (
              <pre className="max-h-32 overflow-auto rounded-md border border-border-soft bg-bg-app p-2 text-xs text-text-secondary">
                {selectedNode.error_message}
              </pre>
            ) : null}
          </div>
        ) : selectedArtifact ? (
          <div className="space-y-3">
            <div>
              <h3 className="break-words text-sm font-semibold">{selectedArtifact.filename}</h3>
              <p className="mt-1 text-xs text-text-secondary">
                {selectedArtifact.artifact_type} · {selectedArtifact.content_type} ·{' '}
                {formatBytes(selectedArtifact.size_bytes)}
              </p>
            </div>
            <KeyValueGrid
              data={selectedArtifact.lineage}
              empty={t.workflowExt.inspector.noMetadata}
            />
            {hasDownload ? (
              <Button type="button"
                variant="outline"
                onClick={() => void downloadSelectedArtifact()}
              >
                <Download className="h-4 w-4" />
                {t.workflowExt.inspector.downloadArtifact}
              </Button>
            ) : (
              <Alert>
                <AlertDescription>{t.workflowExt.inspector.noDownloadUrl}</AlertDescription>
              </Alert>
            )}
          </div>
        ) : (
          <dl className="grid gap-2 text-xs text-text-secondary">
            <div className="flex justify-between gap-2">
              <dt>{t.workflowExt.inspector.nodes}</dt>
              <dd className="text-text-primary">{nodeCount}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>{t.workflowExt.inspector.artifacts}</dt>
              <dd className="text-text-primary">{artifactCount}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>{t.workflowExt.inspector.validation}</dt>
              <dd className="text-text-primary">{t.workflowExt.inspector.validationNotRun}</dd>
            </div>
            <p className="mt-2 text-text-muted">{t.workflowExt.inspector.selectHint}</p>
          </dl>
        )}

      <JobStatusDrawer
        workflowRunId={workflowRunId}
        readOnly={readOnly}
        selectedNodeId={selectedNode?.id ?? null}
        overrideParams={effectiveParameters}
      />
      <div className="mt-3">
        <ClusterDrafts projectId={projectId} variant="panel" readOnly={readOnly} />
      </div>
      </div>
      </ScrollArea>
      </FramePanel>
    </Frame>
  )
}

type DisplayLanguage = 'en' | 'zh'

function localizedValue(value: unknown, language: DisplayLanguage): string {
  if (!value || typeof value !== 'object') return typeof value === 'string' ? value : ''
  const record = value as Record<string, unknown>
  const selected = record[language] ?? record[language === 'en' ? 'zh' : 'en']
  return typeof selected === 'string' ? selected : ''
}

function roleLabel(role: string, language: DisplayLanguage): string {
  const labels: Record<string, { en: string; zh: string }> = {
    positive_control: { en: 'Sweet positive control', zh: '甜味阳性对照' },
    matched_negative_control: { en: 'Matched negative control', zh: '配对阴性对照' },
    unmatched_negative_control: { en: 'Unmatched negative control', zh: '非匹配阴性对照' },
  }
  return labels[role]?.[language] ?? role
}

function truthLabel(truth: string, language: DisplayLanguage): string {
  if (language === 'zh') return truth === 'sweet' ? '甜味' : '不甜'
  return truth === 'sweet' ? 'sweet' : 'not sweet'
}

function RouteDisplayCatalog({
  parameters,
  language,
}: {
  parameters: Record<string, unknown>
  language: DisplayLanguage
}) {
  const catalog = Array.isArray(parameters.molecule_catalog)
    ? parameters.molecule_catalog.filter(
        (item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'),
      )
    : []
  const routePurpose = localizedValue(parameters.route_purpose, language)
  if (catalog.length === 0 && !routePurpose) return null
  const routeLabel = localizedValue(parameters.route_label, language)
  const routeCode = typeof parameters.route_code === 'string' ? parameters.route_code : ''
  const routeTitle = routeLabel
    ? `${language === 'zh' ? 'Route' : 'Route'} ${routeCode} · ${routeLabel}`
    : routeCode
      ? `Route ${routeCode}`
      : ''
  const displayStatus = typeof parameters.display_catalog_status === 'string'
    ? parameters.display_catalog_status
    : ''
  return (
    <InspectorBlock
      icon={<Network className="h-3.5 w-3.5" />}
      title={language === 'zh' ? '路线与分子目的' : 'Route and molecule purpose'}
    >
      <div className="space-y-2 rounded-md border border-border-soft bg-bg-app p-2" data-testid="route-display-catalog">
        {routeTitle ? <p className="text-xs font-semibold text-text-primary">{routeTitle}</p> : null}
        {routePurpose ? <p className="text-xs leading-relaxed text-text-secondary">{routePurpose}</p> : null}
        {displayStatus ? (
          <p className="text-[10px] uppercase tracking-wide text-text-secondary">
            {language === 'zh' ? '展示状态' : 'Display status'}: {displayStatus}
          </p>
        ) : null}
        {catalog.map((member) => {
          const name = typeof member.display_name === 'string' ? member.display_name : 'Unnamed molecule'
          const role = typeof member.role === 'string' ? member.role : ''
          const truth = typeof member.truth_label === 'string' ? member.truth_label : ''
          const length = typeof member.sequence_length === 'number' ? member.sequence_length : null
          const metrics = member.boltz_3seed_mean && typeof member.boltz_3seed_mean === 'object'
            ? member.boltz_3seed_mean as Record<string, unknown>
            : {}
          const poseSummary = localizedValue(member.pose_summary, language)
          const confidence = typeof metrics.confidence_score === 'number'
            ? metrics.confidence_score.toFixed(3)
            : '—'
          const plddt = typeof metrics.complex_plddt === 'number'
            ? metrics.complex_plddt.toFixed(3)
            : '—'
          return (
            <div key={name} className="rounded border border-border-soft bg-surface-1 p-2">
              <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
                <span className="text-xs font-semibold text-text-primary">{name}</span>
                <span className="text-[10px] text-text-secondary">
                  {roleLabel(role, language)} · {truthLabel(truth, language)}
                </span>
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-text-secondary">
                {localizedValue(member.purpose, language)}
              </p>
              <p className="mt-1 text-[10px] text-text-secondary">
                {length == null ? '' : `${length} aa · `}
                Boltz 3-seed: confidence {confidence}, pLDDT {plddt}
              </p>
              {poseSummary ? (
                <p className="mt-1 text-[10px] leading-relaxed text-text-secondary">
                  {language === 'zh' ? '姿态：' : 'Pose: '}{poseSummary}
                </p>
              ) : null}
            </div>
          )
        })}
      </div>
    </InspectorBlock>
  )
}

function InspectorBlock({
  icon,
  title,
  children,
}: {
  icon: ReactNode
  title: string
  children: ReactNode
}) {
  return (
    <div>
      <h4 className="mb-2 flex items-center gap-1.5 text-xs font-medium text-text-secondary">
        {icon}
        {title}
      </h4>
      {children}
    </div>
  )
}

function KeyValueGrid({ data, empty }: { data: Record<string, unknown>; empty: string }) {
  const entries = Object.entries(data).filter(
    ([, value]) => value !== undefined && value !== null && value !== '',
  )
  if (entries.length === 0) {
    return (
      <p className="rounded border border-dashed border-border-soft p-3 text-xs text-text-secondary">
        {empty}
      </p>
    )
  }
  return (
    <dl className="grid gap-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-md border border-border-soft bg-bg-app p-2">
          <dt className="text-[10px] uppercase tracking-wide text-text-secondary">{key}</dt>
          <dd className="mt-1 break-words text-xs text-text-primary">
            {typeof value === 'object' ? JSON.stringify(value) : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  )
}
