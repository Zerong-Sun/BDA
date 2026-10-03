import type { HighlightedResidue } from './types'

export function parseResidueSelection(text: string): HighlightedResidue[] {
  const residues = new Map<string, HighlightedResidue>()
  for (const token of text.trim().split(/[\s,;]+/)) {
    const match = token.match(/^([A-Za-z0-9]+):(-?\d+)$/)
    if (!match || !Number.isSafeInteger(Number(match[2]))) throw new Error('Use chain:residue, for example A:56 or A:56, A:57.')
    const residue = { chainId: match[1], seq: Number(match[2]) }
    residues.set(`${residue.chainId}:${residue.seq}`, residue)
  }
  return [...residues.values()]
}
