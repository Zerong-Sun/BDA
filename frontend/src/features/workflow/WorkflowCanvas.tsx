import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyEdgeChanges,
  useEdgesState,
  useNodesState,
  type Connection,
  type EdgeTypes,
  type EdgeChange,
  type Node,
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
import { saveWorkflowLayout, addWorkflowNode } from '../../lib/api/workflow'
import { useAppStore } from '../../lib/store/appStore'
import { themeColor } from '../../lib/theme/themeColor'
import { useI18n } from '../../lib/i18n'

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
  ) => Promise<void>
  addRecommendedWorkflow: (steps: RecommendedWorkflowStep[], goal: string) => Promise<number>
}

interface WorkflowCanvasProps {
  initialNodes?: BdaWorkflowNode[]
  initialEdges?: BdaWorkflowEdge[]
  workflowRunId?: string
  readOnly?: boolean
  onNodeAdded?: () => void
  onLayoutSaved?: () => void
  onNodeSelected?: (nodeId: string | null) => void
}

export const WorkflowCanvas = forwardRef<WorkflowCanvasHandle, WorkflowCanvasProps>(
  function WorkflowCanvas(
    {
      initialNodes,
      initialEdges,
      workflowRunId,
      readOnly = false,
      onNodeAdded,
      onLayoutSaved,
      onNodeSelected,
    },
    ref,
  ) {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes ?? [])
    const [edges, setEdges] = useEdgesState(initialEdges ?? [])
    const [addingNode, setAddingNode] = useState(false)
    useAppStore((s) => s.themePreference)
    const { t } = useI18n()
    const gridColor = themeColor('--border-soft', '#202020')
    const accentColor = themeColor('--accent', '#D08A2A')
    const maskColor = themeColor('--border-soft', 'rgba(0,0,0,0.45)')
    const saveTimer = useRef<number | null>(null)
    const isInitialMount = useRef(true)
    const nodesRef = useRef(nodes)
    const edgesRef = useRef(edges)
    nodesRef.current = nodes
    edgesRef.current = edges

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
        const retained = current.filter((edge) => incomingIds.has(edge.id))
        const retainedIds = new Set(retained.map((e) => e.id))
        const added = incoming.filter((edge) => !retainedIds.has(edge.id))
        return [...retained, ...added]
      })
    }, [initialNodes, initialEdges, setNodes, setEdges])

    const persistLayout = useCallback(
      (currentNodes: Node[], currentEdges: BdaWorkflowEdge[]) => {
        if (!workflowRunId) return
        if (saveTimer.current) window.clearTimeout(saveTimer.current)
        saveTimer.current = window.setTimeout(() => {
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
            .catch(() => undefined)
        }, 500)
      },
      [workflowRunId, onLayoutSaved],
    )

    const onEdgesChange = useCallback(
      (changes: EdgeChange<BdaWorkflowEdge>[]) => {
        if (readOnly) return
        setEdges((current) => {
          const next = applyEdgeChanges(changes, current)
          if (changes.some((change) => change.type === 'remove')) {
            persistLayout(nodesRef.current, next)
          }
          return next
        })
      },
      [persistLayout, readOnly, setEdges],
    )

    const onConnect = useCallback(
      (connection: Connection) => {
        if (readOnly) return
        setEdges((eds) => {
          const next = addEdge({ ...connection, type: 'workflowEdge', animated: true }, eds)
          persistLayout(nodesRef.current, next)
          return next
        })
      },
      [readOnly, setEdges, persistLayout],
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
    const flowKey = useMemo(
      () => `${nodes.map((node) => node.id).join('|') || 'empty-workflow'}::${edges.map((edge) => edge.id).join('|')}`,
      [nodes, edges],
    )

    return (
      <Frame variant="inverse" spacing="xs" className="h-[min(72vh,760px)] min-h-[34rem]">
        <FramePanel className="relative overflow-hidden bg-bg-canvas p-0">
        {readOnly ? (
          <p className="border-b border-border-soft px-3 py-2 text-xs text-text-secondary">
            {t.workflowExt.canvas.readOnlyBanner}
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
        ) : (
          <div className="pointer-events-none absolute left-3 top-3 z-[1] max-w-[calc(100%-1.5rem)] rounded-md border border-border-soft bg-bg-app/85 px-3 py-2 text-xs text-text-secondary backdrop-blur">
            <p>{t.workflowExt.canvas.connectHint}</p>
            <div
              className="mt-2 flex flex-wrap gap-x-3 gap-y-1"
              aria-label={t.workflowExt.canvas.statusLegendAria}
            >
              {statusLegendKeys.map(([status, labelKey, borderClass]) => (
                <span key={status} className="inline-flex items-center gap-1">
                  <span className={`h-3 w-3 rounded border-2 ${borderClass}`} aria-hidden="true" />
                  {t.shared.status[labelKey]}
                </span>
              ))}
            </div>
          </div>
        )}
        <ReactFlow
          key={flowKey}
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => onNodeSelected?.(node.id)}
          onPaneClick={() => onNodeSelected?.(null)}
          onNodeDragStop={onNodeDragStop}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={proOptions}
          nodesDraggable={!readOnly}
          nodesConnectable={!readOnly}
          edgesFocusable={!readOnly}
          edgesReconnectable={!readOnly}
          panOnScroll
          selectionOnDrag={false}
        >
          <Background gap={20} color={gridColor} style={{ opacity: 0.15 }} />
          <MiniMap
            nodeColor={accentColor}
            maskColor={maskColor}
            className="!bg-surface-1 !border-border-soft"
          />
          <Controls className="!bg-surface-1 !border-border-soft !shadow-none [&>button]:!bg-surface-1 [&>button]:!border-border-soft [&>button]:!text-text-primary" />
        </ReactFlow>
        </FramePanel>
      </Frame>
    )
  },
)
