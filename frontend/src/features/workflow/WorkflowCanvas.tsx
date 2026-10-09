import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  applyEdgeChanges,
  useEdgesState,
  useNodesState,
  type Connection,
  type EdgeTypes,
  type EdgeChange,
  type Node,
  type NodeChange,
  type NodeTypes,
} from '@xyflow/react'
import { CursorClick, SpinnerGap } from '@phosphor-icons/react'
import { Frame, FramePanel } from '../../components/reui/frame'
import { WorkflowNodeCard } from './WorkflowNode'
import { WorkflowEdge } from './WorkflowEdge'
import {
  nodeTemplates,
  type BdaWorkflowEdge,
  type BdaWorkflowNode,
  type NodeTemplate,
  type RecommendedWorkflowStep,
  type WorkflowNodeData,
} from './workflowTypes'
import { useToastStore } from '../../components/ui/toastStore'
import { saveWorkflowLayout, addWorkflowNode, getWorkflowGraph } from '../../lib/api/workflow'
import { saveConnections } from '../../lib/api/workflowGates'
import { useAppStore } from '../../lib/store/appStore'
import { themeColor } from '../../lib/theme/themeColor'
import { useI18n } from '../../lib/i18n'
import { workflowOverview } from './workflowOverview'

const nodeTypes: NodeTypes = { workflowNode: WorkflowNodeCard }
const edgeTypes: EdgeTypes = { workflowEdge: WorkflowEdge }

const statusLegendKeys = [
  ['not_started', 'notStarted', 'border-border-soft'],
  ['queued', 'queued', 'border-accent-2/50'],
  ['running', 'running', 'border-info'],
  ['completed', 'completed', 'border-success/50'],
  ['failed', 'failed', 'border-danger/50'],
] as const

export interface WorkflowCanvasHandle {
  addNodeFromTemplate: (
    template: NodeTemplate,
    nodeName: string,
    methods: string[],
    parameters: Record<string, unknown>,
  ) => Promise<string | undefined>
  addRecommendedWorkflow: (steps: RecommendedWorkflowStep[], goal: string) => Promise<number>
}

interface WorkflowCanvasProps {
  initialNodes?: BdaWorkflowNode[]
  initialEdges?: BdaWorkflowEdge[]
  workflowRunId?: string
  readOnly?: boolean
  overview?: boolean
  onNodeAdded?: () => void
  onLayoutSaved?: () => void
  onConnectionRequested?: (connection: Connection) => void
  onEdgesRemoved?: (ids: string[]) => Promise<void>
  onEdgeSelected?: (edgeId: string) => void
  onNodeSelected?: (nodeId: string | null) => void
  /**
   * The node the page considers selected - from `?node=` - so a linked or
   * reloaded node is highlighted on the canvas, not only in the inspector.
   * `undefined` leaves the canvas to manage its own selection.
   */
  selectedNodeId?: string | null
}

export const WorkflowCanvas = forwardRef<WorkflowCanvasHandle, WorkflowCanvasProps>(
  function WorkflowCanvas(
    {
      initialNodes,
      initialEdges,
      workflowRunId,
      readOnly = false,
      overview = false,
      onNodeAdded,
      onLayoutSaved,
      onNodeSelected,
      onConnectionRequested,
      onEdgesRemoved,
      onEdgeSelected,
      selectedNodeId,
    },
    ref,
  ) {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes ?? [])
    const [edges, setEdges] = useEdgesState(initialEdges ?? [])
    const showToast = useToastStore(s => s.show)
    const [addingNode, setAddingNode] = useState(false)
    useAppStore((s) => s.themePreference)
    const { t, language } = useI18n()
    const gridColor = themeColor('--border-soft', '#202020')
    const accentColor = themeColor('--accent', '#D08A2A')
    const maskColor = themeColor('--border-soft', 'rgba(0,0,0,0.45)')
    const saveTimer = useRef<number | null>(null)
    const isInitialMount = useRef(true)
    const nodesRef = useRef(nodes)
    const edgesRef = useRef(edges)
    nodesRef.current = nodes
    edgesRef.current = edges

    useEffect(() => () => {
      if (saveTimer.current !== null) {
        window.clearTimeout(saveTimer.current)
        saveTimer.current = null
      }
    }, [readOnly, workflowRunId])

    useEffect(() => {
      if (!initialNodes) return

      if (isInitialMount.current) {
        isInitialMount.current = false
        setNodes(initialNodes)
        setEdges(initialEdges ?? [])
        return
      }

      if (initialNodes.length === 0) {
        setNodes([])
        setEdges(initialEdges ?? [])
        return
      }

      // Merge: preserve positions of existing nodes, add new ones from polling
      const existingPositions = new Map(
        nodesRef.current.map((n) => [n.id, n.position]),
      )

      setNodes((current) => {
        const currentById = new Map(current.map((node) => [node.id, node]))
        return initialNodes.map((node) => {
          const existing = currentById.get(node.id)
          return {
            ...node,
            position: existingPositions.get(node.id) ?? node.position,
            selected: existing?.selected,
          }
        })
      })

      setEdges((current) => {
        const incoming = initialEdges ?? []
        const incomingIds = new Set(incoming.map((e) => e.id))
        const retained = current.filter((edge) => incomingIds.has(edge.id)).map(edge => ({ ...incoming.find(e => e.id === edge.id)!, selected: edge.selected }))
        const retainedIds = new Set(retained.map((e) => e.id))
        const added = incoming.filter((edge) => !retainedIds.has(edge.id))
        return [...retained, ...added]
      })
    }, [initialNodes, initialEdges, setNodes, setEdges])

    // The page's selection, reflected onto the canvas. `nodes.length` is a
    // dependency so a node linked before the graph loaded is highlighted once
    // it arrives. Written with `setNodes`, which emits no node changes, so this
    // cannot echo back through `handleNodesChange`.
    const nodeCount = nodes.length
    useEffect(() => {
      if (selectedNodeId === undefined) return
      setNodes((current) => {
        let changed = false
        const next = current.map((node) => {
          const selected = node.id === selectedNodeId
          if (Boolean(node.selected) === selected) return node
          changed = true
          return { ...node, selected }
        })
        return changed ? next : current
      })
    }, [nodeCount, selectedNodeId, setNodes])

    // Keyboard selection. React Flow selects a focused node on Enter or Space
    // inside its own store and never calls `onNodeClick`, so a keyboard user
    // could highlight a node without the inspector or the URL ever hearing of
    // it. Only selections are forwarded: deselection also happens as a side
    // effect of clicking an edge, and forwarding that would clear the edge the
    // person just chose. Clearing is the pane click and Escape, below.
    const handleNodesChange = useCallback(
      (changes: NodeChange<BdaWorkflowNode>[]) => {
        onNodesChange(changes)
        const picked = changes.find((change) => change.type === 'select' && change.selected)
        if (picked && picked.type === 'select') onNodeSelected?.(picked.id)
      },
      [onNodeSelected, onNodesChange],
    )

    const persistLayout = useCallback(
      (currentNodes: Node[], currentEdges: BdaWorkflowEdge[]) => {
        if (!workflowRunId || readOnly) return
        if (saveTimer.current) window.clearTimeout(saveTimer.current)
        saveTimer.current = window.setTimeout(() => {
          saveTimer.current = null
          void saveWorkflowLayout(workflowRunId, {
            nodes: currentNodes.map((node) => ({
              id: node.id,
              position: node.position,
            })),
            edges: currentEdges.map((edge) => ({
              source: edge.source,
              target: edge.target,
            })),
          })
            .then(() => onLayoutSaved?.())
            .catch(error => showToast(error instanceof Error ? error.message : 'Layout save failed', 'error'))
        }, 500)
      },
      [workflowRunId, readOnly, onLayoutSaved, showToast],
    )

    const onEdgesChange = useCallback(
      (changes: EdgeChange<BdaWorkflowEdge>[]) => {
        if (readOnly) return
        const removed = changes.filter(c => c.type === 'remove').map(c => c.id)
        if (removed.length) {
          void onEdgesRemoved?.(removed).catch(error => showToast(error.message, 'error'))
          return
        }
        setEdges(current => applyEdgeChanges(changes, current))
      },
      [readOnly, setEdges, onEdgesRemoved, showToast],
    )

    const onConnect = useCallback(
      (connection: Connection) => {
        if (readOnly) return
        onConnectionRequested?.(connection)
      },
      [readOnly, onConnectionRequested],
    )

    const onNodeDragStop = useCallback(() => {
      persistLayout(nodesRef.current, edgesRef.current)
    }, [persistLayout])

    const addNodeFromTemplate = useCallback(
      async (template: NodeTemplate, nodeName: string, methods: string[], parameters: Record<string, unknown>) => {
        if (addingNode) return
        setAddingNode(true)

        try {
          const currentLen = nodesRef.current.length

          // Calculate position with staggering to avoid overlap
          const col = currentLen % 3
          const row = Math.floor(currentLen / 3) % 4
          const x = 80 + col * 260
          const y = 120 + row * 170 + col * 24

          if (!workflowRunId || readOnly) {
            const id = `custom-${template.id}-${Date.now()}`
            const newNode: Node = {
              id,
              type: 'workflowNode',
              position: { x, y },
              data: {
                label: nodeName,
                description: template.body,
                icon: template.icon,
                status: 'demo' as const,
                footer: methods.join(' · '),
                resource: template.resource,
                methods,
                parameters,
              } satisfies WorkflowNodeData,
            }
            setNodes((nds) => [...nds, newNode] as BdaWorkflowNode[])
            return
          }

          const created = await addWorkflowNode(workflowRunId, {
            node_type: template.nodeType,
            key: nodeName,
            model_plugin: template.modelName,
            model_plugin_id: template.pluginId,
            parameters: { methods, ...parameters },
            position: { x, y },
          })
          const newNode: BdaWorkflowNode = {
            id: created.id,
            type: 'workflowNode',
            position: { x, y },
            data: {
              label: created.node_key,
              description: template.body,
              icon: template.icon,
              status: 'not_started',
              footer: methods.join(' · '),
              resource: template.resource,
              methods,
              parameters,
            },
          }
          setNodes((nds) => [...nds, newNode])
          onNodeAdded?.()
          return created.id
        } finally {
          setAddingNode(false)
        }
      },
      [addingNode, readOnly, workflowRunId, setNodes, onNodeAdded],
    )

    const addRecommendedWorkflow = useCallback(
      async (steps: RecommendedWorkflowStep[], goal: string) => {
        if (addingNode || readOnly || steps.length === 0) return 0
        setAddingNode(true)
        try {
          const existing = nodesRef.current
          const branchIndex = Math.floor(existing.length / Math.max(steps.length, 1))
          const baseY = existing.length === 0 ? 110 : 130 + branchIndex * 190
          const createdNodes: BdaWorkflowNode[] = []

          for (const [index, step] of steps.entries()) {
            const template = nodeTemplates[step.templateId]
            const col = index % 3
            const row = Math.floor(index / 3)
            const x = 80 + col * 280
            const y = baseY + row * 210
            const footer = `${step.estimate.current}/${step.estimate.planned} ${step.estimate.unit} · ${step.estimate.duration}`
            const parameters = {
              ...step.parameters,
              copilot_goal: goal,
              planned: step.estimate.planned,
              current: step.estimate.current,
              estimate_unit: step.estimate.unit,
              estimated_time: step.estimate.duration,
            }

            if (!workflowRunId) {
              const localNode: BdaWorkflowNode = {
                id: `planned-${step.templateId}-${Date.now()}-${index}`,
                type: 'workflowNode',
                position: { x, y },
                data: {
                  label: step.name,
                  description: template.body,
                  icon: template.icon,
                  status: 'not_started',
                  footer,
                  resource: template.resource,
                  methods: step.methods,
                  parameters,
                },
              }
              createdNodes.push(localNode)
              continue
            }

            const created = await addWorkflowNode(workflowRunId, {
              node_type: template.nodeType,
              key: step.name,
              model_plugin: template.modelName,
              model_plugin_id: template.pluginId,
              parameters: { methods: step.methods, ...parameters },
              position: { x, y },
            })
            createdNodes.push({
              id: created.id,
              type: 'workflowNode',
              position: { x, y },
              data: {
                label: created.node_key,
                description: template.body,
                icon: template.icon,
                status: 'not_started',
                footer,
                resource: template.resource,
                methods: step.methods,
                parameters,
              },
            })
          }

          const newEdges: BdaWorkflowEdge[] = createdNodes.slice(0, -1).map((node, index) => ({
            id: `e-${node.id}-${createdNodes[index + 1].id}`,
            source: node.id,
            target: createdNodes[index + 1].id,
            sourceHandle: 'output',
            targetHandle: 'input',
            type: 'workflowEdge',
            animated: index === 0,
          }))

          const nextNodes = [...nodesRef.current, ...createdNodes] as BdaWorkflowNode[]
          const nextEdges = [...edgesRef.current, ...newEdges] as BdaWorkflowEdge[]
          setNodes(nextNodes)
          setEdges(nextEdges)
          if (workflowRunId && !readOnly) {
            const latest = await getWorkflowGraph(workflowRunId)
            await saveConnections(workflowRunId, [...latest.edges, ...newEdges.map(e => ({ id: e.id, source: e.source, target: e.target }))], latest.workflow.version)
          }
          persistLayout(nextNodes, nextEdges)
          onNodeAdded?.()
          return createdNodes.length
        } finally {
          setAddingNode(false)
        }
      },
      [addingNode, readOnly, workflowRunId, setNodes, setEdges, persistLayout, onNodeAdded],
    )

    useImperativeHandle(ref, () => ({ addNodeFromTemplate, addRecommendedWorkflow }), [
      addNodeFromTemplate,
      addRecommendedWorkflow,
    ])

    const proOptions = useMemo(() => ({ hideAttribution: true }), [])
    // Node deletion has no canvas persistence handler. React Flow's default
    // Backspace removal would only hide server nodes locally (even read-only
    // ones) and can also remove their connections. Keep those nodes inspectable.
    const renderedNodes = useMemo(() => nodes.map(node => ({ ...node, deletable: false })), [nodes])
    const overviewGraph = useMemo(() => workflowOverview(renderedNodes, edges), [renderedNodes, edges])
    const completedCount = nodes.filter(node => node.data.status === 'completed').length
    const activeStatuses = [...new Set(nodes.map(node => node.data.status))]
    const flowKey = useMemo(
      () => `${overview ? 'overview' : 'workbench'}::${nodes.map((node) => node.id).join('|') || 'empty-workflow'}::${edges.map((edge) => edge.id).join('|')}`,
      [overview, nodes, edges],
    )

    // `h-full` rather than a viewport fraction: the page gives the canvas column a
    // height, and a second independent one left the cell short of its own row and the
    // graph zoomed further out than it needed to be. The min-height still applies on
    // narrow layouts, where the column is not height-constrained.
    return (
      <Frame variant="inverse" spacing="xs" className="h-full min-h-[34rem]">
        <FramePanel className="relative flex h-full flex-col overflow-hidden bg-bg-canvas p-0">
        {/* Banner and legend sit above the graph rather than floating on it. As overlays
            they covered the top-left corner of the route permanently, and with both
            present the legend was drawn straight over the read-only sentence. */}
        {overview ? <div className="flex shrink-0 flex-wrap items-center justify-between gap-4 border-b border-border-soft bg-surface-1 px-6 py-5">
          <div><h2 className="text-lg font-semibold text-text-primary">{language === 'zh' ? '流程总览' : 'Workflow overview'}</h2><p className="mt-1 text-xs text-text-secondary">{language === 'zh' ? `${nodes.length} 个步骤 · ${completedCount} 个已完成` : `${nodes.length} stages · ${completedCount} completed`}{edges.length === 0 ? (language === 'zh' ? ' · 无已记录的依赖连线' : ' · Dependency edges not recorded') : ''}</p></div>
          <div className="flex items-center gap-4 text-xs text-text-secondary">{activeStatuses.map(status => <span key={status} className="inline-flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${status === 'completed' ? 'bg-success' : status === 'running' ? 'bg-info' : status === 'failed' ? 'bg-danger' : 'bg-accent-2'}`} />{status === 'requires_review' ? t.shared.status.needsReview : statusLegendKeys.find(item => item[0] === status) ? t.shared.status[statusLegendKeys.find(item => item[0] === status)![1]] : status.replaceAll('_', ' ')}<span className="font-semibold text-text-primary">{nodes.filter(node => node.data.status === status).length}</span></span>)}</div>
        </div> : null}
        {readOnly && !overview ? (
          <p className="shrink-0 border-b border-border-soft px-3 py-2 text-xs text-text-secondary">
            {language === 'zh' ? '当前工作流只读。可选择节点和连线查看详情。' : 'This workflow is read-only. Select nodes and connections to inspect details.'}
          </p>
        ) : null}
        {addingNode ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-bg-app/60 backdrop-blur-sm">
            <div className="flex items-center gap-2 rounded-lg border border-border-soft bg-surface-1 px-4 py-3 text-sm text-text-primary shadow-lg">
              <SpinnerGap className="h-4 w-4 animate-spin text-accent" />
              {t.workflowExt.canvas.addingNode}
            </div>
          </div>
        ) : null}
        {nodes.length === 0 ? (
          <div className="pointer-events-none absolute inset-0 z-[1] flex items-center justify-center p-6">
            <div className="max-w-md rounded-lg border border-dashed border-border-soft bg-bg-app/85 p-5 text-center shadow-lg backdrop-blur">
              <CursorClick className="mx-auto mb-3 h-5 w-5 text-accent" />
              <h3 className="text-sm font-semibold text-text-primary">{t.workflowExt.canvas.emptyTitle}</h3>
              <p className="mt-2 text-xs leading-relaxed text-text-secondary">{t.workflowExt.canvas.emptyBody}</p>
            </div>
          </div>
        ) : !overview ? (
          <div className="shrink-0 border-b border-border-soft px-3 py-1.5 text-[11px] text-text-secondary">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span>{t.workflowExt.canvas.connectHint}</span>
              <span
                className="flex flex-wrap items-center gap-x-3 gap-y-1"
                aria-label={t.workflowExt.canvas.statusLegendAria}
              >
                {statusLegendKeys.map(([status, labelKey, borderClass]) => (
                  <span key={status} className="inline-flex items-center gap-1">
                    <span className={`h-3 w-3 rounded border-2 ${borderClass}`} aria-hidden="true" />
                    {t.shared.status[labelKey]}
                  </span>
                ))}
              </span>
            </div>
          </div>
        ) : null}
        <ReactFlow
          className="min-h-0 flex-1"
          key={flowKey}
          nodes={overview ? overviewGraph.nodes : renderedNodes}
          edges={overview ? overviewGraph.edges : edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={onEdgesChange}
          onKeyDown={(event) => {
            // Escape clears the selection from anywhere on the canvas, except
            // while typing in a field inside a node, where it belongs to the field.
            if (event.key !== 'Escape') return
            if ((event.target as HTMLElement).closest('input, textarea, select, [contenteditable="true"]')) return
            onNodeSelected?.(null)
          }}
          onConnect={onConnect}
          onEdgeClick={(_, edge) => onEdgeSelected?.(edge.id)}
          onNodeClick={(_, node) => onNodeSelected?.(node.id)}
          onPaneClick={() => onNodeSelected?.(null)}
          onNodeDragStop={onNodeDragStop}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          minZoom={0.1}
          fitViewOptions={{ padding: overview ? 0.07 : 0.2, minZoom: 0.1, maxZoom: overview ? 1.25 : 2 }}
          proOptions={proOptions}
          nodesDraggable={!readOnly && !overview}
          nodesConnectable={!readOnly && !overview}
          edgesFocusable={false}
          edgesReconnectable={false}
          deleteKeyCode={readOnly || overview ? null : 'Backspace'}
          panOnScroll
          selectionOnDrag={false}
        >
          <Background gap={overview ? 24 : 20} color={gridColor} style={{ opacity: overview ? 0.08 : 0.15 }} />
          {/* Default minimap is 200x150 and covers a corner of the route on the column
              widths this page uses; a route of a handful of stages does not need that
              much of the canvas spent on an overview of itself. */}
          {!overview ? <MiniMap
            nodeColor={accentColor}
            maskColor={maskColor}
            pannable
            zoomable
            style={{ width: 128, height: 88 }}
            // Hidden on phones: the canvas there is short enough that the overview covers
            // a quarter of the route it is meant to summarise.
            className="!hidden !bg-surface-1 !border-border-soft md:!block"
          /> : null}
          <Controls showInteractive={!overview} fitViewOptions={{ padding: overview ? 0.07 : 0.2, minZoom: 0.1, maxZoom: overview ? 1.25 : 2 }} className="!bg-surface-1 !border-border-soft !shadow-none [&>button]:!bg-surface-1 [&>button]:!border-border-soft [&>button]:!text-text-primary" />
        </ReactFlow>
        </FramePanel>
      </Frame>
    )
  },
)
