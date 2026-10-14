import type { HighlightedResidue } from './types'

export function parseResidueSelection(text: string): HighlightedResidue[] {
  const residues = new Map<string, HighlightedResidue>()
  for (const token of text.trim().split(/[\s,;]+/)) {
    const match = token.match(/^([A-Za-z0-9]+):(-?\d+)([A-Za-z]?)$/)
    if (!match || !Number.isSafeInteger(Number(match[2]))) throw new Error('Use chain:residue, for example A:56 or A:56A, A:57.')
    const residue = { chainId: match[1], seq: Number(match[2]), ...(match[3] ? { insertionCode: match[3] } : {}) }
    residues.set(`${residue.chainId}:${residue.seq}:${residue.insertionCode ?? ''}`, residue)
  }
  return [...residues.values()]
}
