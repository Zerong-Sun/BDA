import { describe, expect, it } from 'vitest'
import { WorkflowNodeSchema } from '../../lib/schemas/workflow'
import {
  footerFromMetrics,
  mapApiGraphToGraph,
  mapApiNodesToGraph,
  mapStatusForTest,
} from './workflowMapper'

function apiNode(overrides: Record<string, unknown>) {
  return WorkflowNodeSchema.parse({
    id: 'n1',
    workflow_run_id: 'r1',
    node_type: 'target_intake',
    node_key: 'target_protein',
    model_plugin: 'target-intake',
    model_plugin_id: null,
    container_image: null, command: null, queue: null, error_message: null,
    status: 'draft',
    parameters: {}, position: null, version: 1,
    created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
    ...overrides,
  })
}

describe('workflowMapper', () => {
  it('maps every API node status onto a canvas status', () => {
    // The API vocabulary, not the retired 'completed'/'staging' one the seeding script
    // used to emit. A value the pipeline can return must never fall through.
    expect(mapStatusForTest('draft')).toBe('not_started')
    expect(mapStatusForTest('pending')).toBe('queued')
    expect(mapStatusForTest('dispatching')).toBe('queued')
    expect(mapStatusForTest('queued')).toBe('queued')
    expect(mapStatusForTest('running')).toBe('running')
    expect(mapStatusForTest('collecting')).toBe('running')
    expect(mapStatusForTest('succeeded')).toBe('completed')
    expect(mapStatusForTest('failed')).toBe('failed')
    expect(mapStatusForTest('cancelled')).toBe('skipped')
    expect(mapStatusForTest('requires_review')).toBe('requires_review')
  })

  it('falls back to not_started only for statuses outside the contract', () => {
    expect(mapStatusForTest('unknown')).toBe('not_started')
  })

  it('builds edges from the graph the API returned, not from node order', () => {
    const nodes = [
      apiNode({ id: 'n1', node_key: 'intake', status: 'succeeded' }),
      apiNode({ id: 'n2', node_key: 'design', node_type: 'backbone_generation', status: 'running' }),
      apiNode({ id: 'n3', node_key: 'score', node_type: 'scoring', status: 'draft' }),
    ]

    const graph = mapApiGraphToGraph(nodes, [
      { source: 'intake', target: 'score' },
      { source: 'intake', target: 'design' },
    ])

    expect(graph.nodes).toHaveLength(3)
    expect(graph.edges.map((edge) => [edge.source, edge.target])).toEqual([
      ['n1', 'n3'],
      ['n1', 'n2'],
    ])
  })

  it('returns no edges when the workflow has none', () => {
    expect(mapApiGraphToGraph([apiNode({})], []).edges).toEqual([])
  })

  it('uses imported display metadata and confidence metrics', () => {
    const node = apiNode({
      node_type: 'fold_prediction',
      node_key: 'brazzein_alphafold2',
      model_plugin: 'AlphaFold2',
      status: 'running',
      parameters: {
        display_name: 'Brazzein AlphaFold2',
        description: 'Validated confidence results.',
        metrics: { folded: 316, mean_plddt: 76.64 },
      },
    })

    const nodes = mapApiNodesToGraph([node])
    expect(nodes[0]?.data.label).toBe('Brazzein AlphaFold2')
    expect(nodes[0]?.data.description).toBe('Validated confidence results.')
    expect(footerFromMetrics(node)).toBe('316 folded · 76.64 mean pLDDT')
  })

  it('gives the receptor-conditioned stages their own icon and resource class', () => {
    // Without these, every stage of the third route falls back to database/local and the
    // canvas shows a GPU docking run as a local data node.
    const nodes = mapApiNodesToGraph([
      apiNode({ id: 'c1', node_key: 'receptor_hotspot_map', node_type: 'interface_constraints' }),
      apiNode({ id: 'c2', node_key: 'receptor_backbone_generation', node_type: 'complex_backbone_generation' }),
      apiNode({ id: 'c3', node_key: 'receptor_sequence_design', node_type: 'interface_sequence_design' }),
      apiNode({ id: 'c4', node_key: 'receptor_complex_prediction', node_type: 'complex_prediction' }),
      apiNode({ id: 'c5', node_key: 'receptor_ensemble_docking', node_type: 'ensemble_docking' }),
      apiNode({ id: 'c6', node_key: 'receptor_interface_scoring', node_type: 'interface_physics_scoring' }),
    ])

    expect(nodes.map((node) => [node.data.icon, node.data.resource])).toEqual([
      ['file-json', 'local'],
      ['wand-sparkles', 'gpu'],
      ['dna', 'gpu'],
      ['scan-search', 'gpu'],
      ['activity', 'gpu'],
      ['activity', 'cpu'],
    ])
    // Distinct columns, so the branch lays out left to right rather than stacking.
    expect(new Set(nodes.map((node) => node.position.x)).size).toBe(6)
  })

  it('gives the de novo protocol stages their own icon and resource class', () => {
    const nodes = mapApiNodesToGraph([
      apiNode({ id: 'p1', node_key: 'route_b_geometry_check', node_type: 'geometry_check' }),
      apiNode({ id: 'p2', node_key: 'route_a_motif_extraction', node_type: 'motif_extraction' }),
      apiNode({ id: 'p3', node_key: 'route_b_domain_design', node_type: 'binder_generation' }),
      apiNode({ id: 'p4', node_key: 'route_a_ip_foldspace_filter', node_type: 'ip_filter' }),
      apiNode({ id: 'p5', node_key: 'route_b_linker_ladder', node_type: 'linker_enumeration' }),
      apiNode({ id: 'p6', node_key: 'route_c_differential_af2', node_type: 'differential_scoring' }),
      apiNode({ id: 'p7', node_key: 'route_c_sequence_developability', node_type: 'developability_filter' }),
      apiNode({ id: 'p8', node_key: 'route_c_enhanced_sampling', node_type: 'enhanced_sampling' }),
    ])

    expect(nodes.map((node) => [node.data.icon, node.data.resource])).toEqual([
      ['activity', 'local'],
      ['file-json', 'local'],
      ['wand-sparkles', 'gpu'],
      ['filter', 'cpu'],
      ['dna', 'cpu'],
      ['scan-search', 'gpu'],
      ['filter', 'cpu'],
      ['activity', 'gpu'],
    ])
  })

  it('reports a missing plugin instead of a progress count', () => {
    const node = apiNode({
      node_key: 'receptor_ensemble_docking',
      node_type: 'ensemble_docking',
      parameters: {
        planned: 500,
        current: 0,
        estimate_unit: 'pose ensembles',
        missing_model_plugins: ['RosettaDock', 'HADDOCK'],
      },
    })

    expect(footerFromMetrics(node)).toBe('Needs plugin: RosettaDock, HADDOCK')
  })

  it('keeps the progress footer when nothing is missing', () => {
    const node = apiNode({
      node_key: 'receptor_complex_prediction',
      node_type: 'complex_prediction',
      parameters: {
        planned: 500,
        current: 0,
        estimate_unit: 'complex predictions',
        missing_model_plugins: [],
      },
    })

    expect(footerFromMetrics(node)).toBe('0/500 complex predictions')
  })
})
