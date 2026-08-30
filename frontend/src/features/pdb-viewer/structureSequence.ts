import { StructureElement, StructureProperties, Unit } from 'molstar/lib/mol-model/structure'
import type { PluginContext } from 'molstar/lib/mol-plugin/context'

export interface ChainSequence {
  chainId: string
  sequence: string
  residueCount: number
}

const ONE_LETTER: Record<string, string> = {
  ALA: 'A', ARG: 'R', ASN: 'N', ASP: 'D', CYS: 'C', GLN: 'Q', GLU: 'E', GLY: 'G',
  HIS: 'H', ILE: 'I', LEU: 'L', LYS: 'K', MET: 'M', PHE: 'F', PRO: 'P', SER: 'S',
  THR: 'T', TRP: 'W', TYR: 'Y', VAL: 'V', SEC: 'U', PYL: 'O',
  // Protonation and modification variants that force-fields and preparation
  // pipelines emit; they are the same residue as far as a sequence is concerned.
  HID: 'H', HIE: 'H', HIP: 'H', HSD: 'H', HSE: 'H', HSP: 'H',
  CYX: 'C', CYM: 'C', ASH: 'D', GLH: 'E', LYN: 'K', ARN: 'R', MSE: 'M',
  // Post-translational modifications seen in deposited structures. Mapping known
  // residues avoids false mismatches against canonical UniProt sequences.
  PCA: 'Q', SEP: 'S', TPO: 'T', PTR: 'Y', CSO: 'C', CME: 'C', OCS: 'C',
  MLY: 'K', M3L: 'K', ALY: 'K', KCX: 'K', HYP: 'P', TYS: 'Y',
  DA: 'A', DC: 'C', DG: 'G', DT: 'T', DU: 'U', A: 'A', C: 'C', G: 'G', U: 'U',
}

const FASTA_LINE_WIDTH = 60

function residueCode(compId: string): string {
  return ONE_LETTER[compId.toUpperCase()] ?? 'X'
}

/**
 * Walks the first loaded structure and returns one entry per author chain.
 * Only polymer residues are collected — waters, ions and ligands would
 * otherwise show up as runs of `X`.
 */
export function extractChainSequences(plugin: PluginContext): ChainSequence[] {
  const hierarchy = plugin.managers.structure.hierarchy.current
  const structure = hierarchy.structures[0]?.cell?.obj?.data
  if (!structure) return []

  const order: string[] = []
  const byChain = new Map<string, Map<number, string>>()
  const location = StructureElement.Location.create(structure)

  for (const unit of structure.units) {
    if (!Unit.isAtomic(unit)) continue
    location.unit = unit
    const residueIndex = unit.model.atomicHierarchy.residueAtomSegments.index
    const { elements } = unit
    let previousResidue = -1

    for (let index = 0; index < elements.length; index += 1) {
      const element = elements[index]
      const currentResidue = residueIndex[element]
      if (currentResidue === previousResidue) continue
      previousResidue = currentResidue

      location.element = element
      if (StructureProperties.entity.type(location) !== 'polymer') continue

      const chainId = StructureProperties.chain.auth_asym_id(location)
      const seqId = StructureProperties.residue.auth_seq_id(location)
      const compId = StructureProperties.atom.label_comp_id(location)

      let residues = byChain.get(chainId)
      if (!residues) {
        residues = new Map<number, string>()
        byChain.set(chainId, residues)
        order.push(chainId)
      }
      if (!residues.has(seqId)) residues.set(seqId, residueCode(compId))
    }
  }

  return order.map((chainId) => {
    const residues = byChain.get(chainId) ?? new Map<number, string>()
    const sequence = [...residues.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([, code]) => code)
      .join('')
    return { chainId, sequence, residueCount: sequence.length }
  }).filter((entry) => entry.residueCount > 0)
}

export function formatFasta(chains: ChainSequence[], label?: string | null): string {
  const name = (label ?? 'structure').trim().replace(/\s+/g, '_') || 'structure'
  return chains
    .map((chain) => {
      const header = `>${name}|Chain_${chain.chainId}|${chain.residueCount}aa`
      const lines: string[] = []
      for (let index = 0; index < chain.sequence.length; index += FASTA_LINE_WIDTH) {
        lines.push(chain.sequence.slice(index, index + FASTA_LINE_WIDTH))
      }
      return [header, ...lines].join('\n')
    })
    .join('\n')
}

/**
 * Clipboard writes need a secure context; older Safari and plain-HTTP hosts
 * fall back to the legacy execCommand path so the button still works there.
 */
export async function copyTextToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* fall through to the legacy path */
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.append(textarea)
    textarea.select()
    const copied = document.execCommand('copy')
    textarea.remove()
    return copied
  } catch {
    return false
  }
}
