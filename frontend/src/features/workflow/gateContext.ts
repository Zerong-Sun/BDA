import type { ModelPlugin } from '../../lib/schemas/registry'
import type { WorkflowEdge } from '../../lib/schemas/workflow'
import { emptyPolicy, type GatePolicy } from './gates'

/** Hints describe the registered port contract; they never silently replace saved rules. */
export function gateContext(edge: WorkflowEdge, source?: ModelPlugin, target?: ModelPlugin) {
  const output = source?.output_ports.find(p => p.name === edge.source_port)
  const input = target?.input_ports.find(p => p.name === edge.target_port)
  const structure = output?.kind === 'protein_structure'
  const sequence = output?.kind === 'protein_sequence'
  const integrity = !!output && ['params', 'msa', 'ligand'].includes(output.kind)
  const parser = source?.output_parser
  const metrics = parser === 'proteinmpnn_fasta' ? ['score', 'global_score', 'seq_recovery']
    : parser === 'rosetta_interface' ? ['dG_separated', 'dSASA_int', 'sc_value', 'packstat', 'total_score']
    : parser === 'alphafold2_superfold' ? ['plddt', 'plddt_min', 'ptm', 'pae_interaction', 'pae']
      : parser === 'alphafold3' ? ['iptm', 'ptm', 'ranking_score']
        : []
  return { source, target, output, input, structure, sequence, integrity, metrics }
}

/** A changed mapping needs a fresh policy. In particular dependency cannot carry ports. */
export function policyForConnection(previous: WorkflowEdge | undefined, next: Pick<WorkflowEdge, 'source' | 'target' | 'source_port' | 'target_port'>): GatePolicy {
  if (!next.source_port || !next.target_port) return { ...emptyPolicy(), mode: 'dependency', configured: true }
  const unchanged = previous && ['source', 'target', 'source_port', 'target_port'].every(
    key => previous[key as keyof typeof next] === next[key as keyof typeof next],
  )
  return unchanged && previous.gate ? previous.gate as GatePolicy : emptyPolicy()
}
