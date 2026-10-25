import { describe, expect, it } from 'vitest'
import { ModelPluginSchema } from '../../lib/schemas/registry'
import type { WorkflowEdge } from '../../lib/schemas/workflow'
import { emptyPolicy } from './gates'
import { gateContext, policyForConnection } from './gateContext'

const plugin = (key: string, kind: string, parser: string | null = null) => ModelPluginSchema.parse({
  id: key, plugin_key: key, plugin_version: '1', name: key, container_image: '', command: '',
  parameter_schema: {}, output_schema: {}, enabled: true, validation_status: 'valid',
  validated_at: null, validation_errors: [], version: 1, created_at: '', updated_at: '', output_parser: parser,
  output_ports: [{name: 'out', kind, artifact_type: kind}], input_ports: [{name: 'in', kind}],
})
const edge = { id: 'e', source: 'a', target: 'b', source_port: 'out', target_port: 'in', gate: { ...emptyPolicy(), configured: true } } as WorkflowEdge

describe('model-aware gate contracts', () => {
  it('changes capabilities and metrics with the actual producer and consumer', () => {
    const mpnn = plugin('mpnn', 'protein_sequence', 'proteinmpnn_fasta')
    const fold = plugin('fold', 'protein_structure', 'alphafold2_superfold')
    const score = plugin('score', 'protein_structure')
    const sequences = gateContext(edge, mpnn, fold)
    expect(sequences.sequence).toBe(true)
    expect(sequences.structure).toBe(false)
    expect(sequences.metrics).toContain('score')
    expect(sequences.metrics).not.toContain('plddt')
    const structures = gateContext(edge, fold, score)
    expect(structures.structure).toBe(true)
    expect(structures.metrics).toContain('plddt')
    expect(structures.target?.name).toBe('score')
    expect(gateContext(edge, plugin('parameters', 'params'), score).integrity).toBe(true)
  })
  it('does not invent metrics when no parser is registered', () => {
    expect(gateContext(edge, plugin('AlphaFold2', 'protein_structure')).metrics).toEqual([])
  })
  it('preserves unchanged rules but resets them when nodes or ports change', () => {
    expect(policyForConnection(edge, edge)).toEqual(edge.gate)
    for (const patch of [{source: 'c'}, {target: 'c'}, {source_port: 'other'}, {target_port: 'other'}]) {
      expect(policyForConnection(edge, {...edge, ...patch}).configured).toBe(false)
    }
  })
  it('converts ordering to a fresh data policy, and data to a portless dependency', () => {
    const ordering = {...edge, source_port: null, target_port: null, gate: {...emptyPolicy(), mode: 'dependency', configured: true}} as WorkflowEdge
    expect(policyForConnection(ordering, edge).mode).toBe('automatic')
    expect(policyForConnection(ordering, edge).configured).toBe(false)
    expect(policyForConnection(edge, ordering)).toMatchObject({mode: 'dependency', configured: true})
  })
})
