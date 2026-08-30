import type { Node, Edge } from '@xyflow/react'

export type WorkflowNodeStatus =
  | 'not_started'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped'
  | 'requires_review'
  | 'demo'

export interface WorkflowNodeData extends Record<string, unknown> {
  label: string
  description: string
  icon: string
  status: WorkflowNodeStatus
  footer: string
  resource?: 'cpu' | 'gpu' | 'local' | 'manual'
  methods?: string[]
  parameters?: Record<string, unknown>
}

export type BdaWorkflowNode = Node<WorkflowNodeData>
export type BdaWorkflowEdge = Edge

export interface NodeTemplate {
  id: string
  icon: string
  title: string
  body: string
  resource: WorkflowNodeData['resource']
  nodeType: string
  modelName?: string
  modelVersion?: string
  pluginId?: string
  parameterSchema?: unknown
}

export interface RecommendedWorkflowStep {
  templateId: keyof typeof nodeTemplates
  name: string
  methods: string[]
  parameters: Record<string, unknown>
  estimate: {
    planned: number
    current: number
    unit: string
    duration: string
  }
}

export const nodeTemplates: Record<string, NodeTemplate> = {
  rf: {
    id: 'rf',
    icon: 'wand-sparkles',
    title: 'Backbone generation',
    body: 'Explore binder geometry with RFdiffusion',
    resource: 'gpu',
    nodeType: 'backbone_generation',
    modelName: 'RFdiffusion',
    modelVersion: 'demo-1.0',
    pluginId: 'plugin_rfdiffusion',
  },
  mpnn: {
    id: 'mpnn',
    icon: 'dna',
    title: 'Sequence design',
    body: 'ProteinMPNN sequence search with diversity constraints',
    resource: 'gpu',
    nodeType: 'sequence_generation',
    modelName: 'ProteinMPNN',
    modelVersion: 'demo-1.0',
    pluginId: 'plugin_proteinmpnn',
  },
  af2: {
    id: 'af2',
    icon: 'scan-search',
    title: 'Fold prediction',
    body: 'AlphaFold2 evaluates complex confidence and interface pAE',
    resource: 'gpu',
    nodeType: 'fold_prediction',
    modelName: 'AlphaFold2',
    modelVersion: 'demo-2.3',
    pluginId: 'plugin_alphafold2',
  },
  af3: {
    id: 'af3',
    icon: 'scan-search',
    title: 'AlphaFold 3 prediction',
    body: 'All-atom complex prediction for non-commercial evaluation branches',
    resource: 'gpu',
    nodeType: 'fold_prediction',
    modelName: 'AlphaFold 3',
    modelVersion: '3.0',
    pluginId: 'plugin_alphafold3',
  },
  boltz: {
    id: 'boltz',
    icon: 'scan-search',
    title: 'Boltz prediction',
    body: 'Open biomolecular complex prediction and affinity-oriented ranking',
    resource: 'gpu',
    nodeType: 'fold_prediction',
    modelName: 'Boltz',
    modelVersion: '2.x',
    pluginId: 'plugin_boltz',
  },
  chai1: {
    id: 'chai1',
    icon: 'scan-search',
    title: 'Chai-1 prediction',
    body: 'Complex prediction with support for restraints and ligand-like context',
    resource: 'gpu',
    nodeType: 'fold_prediction',
    modelName: 'Chai-1',
    modelVersion: '0.6.1',
    pluginId: 'plugin_chai1',
  },
  bindcraft: {
    id: 'bindcraft',
    icon: 'wand-sparkles',
    title: 'BindCraft pipeline',
    body: 'Automated binder design branch with AF2 optimization, MPNN, and PyRosetta filters',
    resource: 'gpu',
    nodeType: 'workflow_pipeline',
    modelName: 'BindCraft',
    modelVersion: '2025.09',
    pluginId: 'plugin_bindcraft',
  },
  rosetta: {
    id: 'rosetta',
    icon: 'activity',
    title: 'Rosetta scoring',
    body: 'Relax and interface scoring for energy and clashes',
    resource: 'cpu',
    nodeType: 'scoring',
    modelName: 'Rosetta',
    modelVersion: 'demo-2026.06',
    pluginId: 'plugin_rosetta',
  },
  filter: {
    id: 'filter',
    icon: 'filter',
    title: 'BDA filters',
    body: 'Rank by interface, solubility, aggregation, expression risk',
    resource: 'cpu',
    nodeType: 'selection',
    modelName: 'BDA filters',
    modelVersion: 'demo-1.0',
  },
  lab: {
    id: 'lab',
    icon: 'flask-conical',
    title: 'Wet-lab validation',
    body: 'Expression, purification, BLI, SEC, thermal shift',
    resource: 'manual',
    nodeType: 'experiment',
  },
}

export const defaultWorkflowNodes: BdaWorkflowNode[] = [
  {
    id: 'target',
    type: 'workflowNode',
    position: { x: 40, y: 60 },
    data: {
      label: 'Target protein',
      description: 'PD-1 structure, interface residues, assay constraints',
      icon: 'database',
      status: 'completed',
      footer: '3/3 inputs confirmed',
      resource: 'local',
    },
  },
  {
    id: 'requirements',
    type: 'workflowNode',
    position: { x: 40, y: 420 },
    data: {
      label: 'Task requirements',
      description: 'Design high-affinity PD-1 binders with developability constraints',
      icon: 'file-json',
      status: 'completed',
      footer: '5/5 constraints parsed',
      resource: 'local',
    },
  },
  {
    id: 'rfdiffusion',
    type: 'workflowNode',
    position: { x: 280, y: 240 },
    data: {
      label: 'Backbone generation',
      description: 'Explore binder geometry with RFdiffusion',
      icon: 'wand-sparkles',
      status: 'running',
      footer: '1,248/18,000 generated',
      resource: 'gpu',
    },
  },
  {
    id: 'mpnn',
    type: 'workflowNode',
    position: { x: 500, y: 240 },
    data: {
      label: 'Sequence design',
      description: 'ProteinMPNN sequence search with diversity constraints',
      icon: 'dna',
      status: 'queued',
      footer: '384/1,248 designed',
      resource: 'gpu',
    },
  },
  {
    id: 'af2',
    type: 'workflowNode',
    position: { x: 720, y: 60 },
    data: {
      label: 'Fold prediction',
      description: 'AlphaFold2 evaluates complex structure and local confidence',
      icon: 'scan-search',
      status: 'not_started',
      footer: '312/384 folded',
      resource: 'gpu',
    },
  },
  {
    id: 'rosetta',
    type: 'workflowNode',
    position: { x: 720, y: 240 },
    data: {
      label: 'Rosetta scoring',
      description: 'Rosetta relax estimates interface energy and clashes',
      icon: 'activity',
      status: 'not_started',
      footer: '120/312 scored',
      resource: 'cpu',
    },
  },
  {
    id: 'filters',
    type: 'workflowNode',
    position: { x: 720, y: 420 },
    data: {
      label: 'BDA filters',
      description: 'Affinity, solubility, aggregation risk, expression risk',
      icon: 'filter',
      status: 'completed',
      footer: '96/384 passed filters',
      resource: 'cpu',
    },
  },
  {
    id: 'wetlab',
    type: 'workflowNode',
    position: { x: 500, y: 420 },
    data: {
      label: 'Wet-lab validation',
      description: 'Expression, purification, BLI, SEC, thermal shift',
      icon: 'flask-conical',
      status: 'completed',
      footer: '9/48 hits confirmed',
      resource: 'manual',
    },
  },
]

export const defaultWorkflowEdges: BdaWorkflowEdge[] = [
  { id: 'e-target-rf', source: 'target', target: 'rfdiffusion', type: 'workflowEdge', animated: true },
  { id: 'e-req-rf', source: 'requirements', target: 'rfdiffusion', type: 'workflowEdge' },
  { id: 'e-rf-mpnn', source: 'rfdiffusion', target: 'mpnn', type: 'workflowEdge', animated: true },
  { id: 'e-mpnn-af2', source: 'mpnn', target: 'af2', type: 'workflowEdge' },
  { id: 'e-af2-rosetta', source: 'af2', target: 'rosetta', type: 'workflowEdge' },
  { id: 'e-rosetta-filters', source: 'rosetta', target: 'filters', type: 'workflowEdge' },
  { id: 'e-filters-wetlab', source: 'filters', target: 'wetlab', type: 'workflowEdge' },
  { id: 'e-wetlab-req', source: 'wetlab', target: 'requirements', type: 'workflowEdge', label: 'feedback' },
]

export function buildRecommendedWorkflow(goal: string): RecommendedWorkflowStep[] {
  const normalized = goal.toLowerCase()
  const isEnzyme = normalized.includes('enzyme') || normalized.includes('酶')
  const isDisplay = normalized.includes('display') || normalized.includes('展示') || normalized.includes('nanocage')
  const designCount = isDisplay ? 12000 : isEnzyme ? 6000 : 10000
  const sequenceCount = Math.max(1200, Math.round(designCount * 0.18))
  const foldedCount = Math.max(300, Math.round(sequenceCount * 0.28))
  const scoredCount = Math.max(120, Math.round(foldedCount * 0.45))
  const orderedCount = isDisplay ? 72 : isEnzyme ? 32 : 48

  return [
    {
      templateId: 'rf',
      name: isDisplay ? 'Assembly backbone generation' : isEnzyme ? 'Scaffold redesign' : 'Backbone generation',
      methods: ['RFdiffusion', 'motif constraints'],
      parameters: {
        goal,
        planned_designs: designCount,
        current_designs: 0,
        estimated_time: isDisplay ? '18-30 GPU hours' : '12-24 GPU hours',
      },
      estimate: { planned: designCount, current: 0, unit: 'backbones', duration: isDisplay ? '18-30h GPU' : '12-24h GPU' },
    },
    {
      templateId: 'mpnn',
      name: 'Sequence design',
      methods: ['ProteinMPNN', 'diversity cap'],
      parameters: {
        planned_sequences: sequenceCount,
        current_sequences: 0,
        temperature: 0.15,
        max_family_ordered: 6,
      },
      estimate: { planned: sequenceCount, current: 0, unit: 'sequences', duration: '1-3h GPU' },
    },
    {
      templateId: 'af2',
      name: isDisplay ? 'Multimer fold prediction' : 'Fold prediction',
      methods: ['AlphaFold2', isDisplay ? 'multimer confidence' : 'complex confidence'],
      parameters: {
        planned_folds: foldedCount,
        current_folds: 0,
        recycles: 3,
        database_preset: 'reduced_dbs',
      },
      estimate: { planned: foldedCount, current: 0, unit: 'folds', duration: '6-16h GPU' },
    },
    {
      templateId: 'rosetta',
      name: 'Rosetta scoring',
      methods: ['relax', 'interface energy'],
      parameters: {
        planned_scores: scoredCount,
        current_scores: 0,
        relax_repeats: 3,
      },
      estimate: { planned: scoredCount, current: 0, unit: 'scores', duration: '2-6h CPU' },
    },
    {
      templateId: 'filter',
      name: isEnzyme ? 'Activity and developability filters' : 'BDA filters',
      methods: ['risk ranking', 'family diversity'],
      parameters: {
        planned_orders: orderedCount,
        current_orders: 0,
        penalize_hydrophobic_patch: true,
        expression_risk_gate: true,
      },
      estimate: { planned: orderedCount, current: 0, unit: 'ordered', duration: '<30m CPU' },
    },
    {
      templateId: 'lab',
      name: isEnzyme ? 'Activity validation' : 'Wet-lab validation',
      methods: isEnzyme ? ['expression', 'activity assay', 'thermal shift'] : ['expression', 'purification', 'BLI/SPR', 'SEC'],
      parameters: {
        planned_assays: orderedCount,
        current_assays: 0,
        expected_turnaround: isEnzyme ? '2-4 weeks' : '3-5 weeks',
      },
      estimate: { planned: orderedCount, current: 0, unit: 'assays', duration: isEnzyme ? '2-4w lab' : '3-5w lab' },
    },
  ]
}
