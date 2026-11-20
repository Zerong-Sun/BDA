import { describe, expect, it, vi } from 'vitest'
import { parsePDB } from 'molstar/lib/mol-io/reader/pdb/parser'
import { trajectoryFromPDB } from 'molstar/lib/mol-model-formats/structure/pdb'
import { Structure, StructureElement, StructureProperties, StructureSelection } from 'molstar/lib/mol-model/structure'
import { Script } from 'molstar/lib/mol-script/script'
import type { PluginContext } from 'molstar/lib/mol-plugin/context'
import { buildResidueQuery, focusResidueById, subscribeResiduePicks } from './structureLoader'
import { extractChainSequences } from './structureSequence'
import { parseResidueSelection } from './residueSelectionParser'
import { parseHotspotResidue } from './types'

async function fixture() {
  const atom = (serial: number, name: string, code: string, x: number) =>
    `ATOM  ${String(serial).padStart(5)}  CA  ${name} A  52${code}   ${x.toFixed(3).padStart(8)}   0.000   0.000  1.00 20.00           C`
  const parsed = await parsePDB([atom(1, 'LYS', ' ', 0), atom(2, 'ARG', 'A', 4), 'END'].join('\n')).run()
  if (parsed.isError) throw new Error(parsed.message)
  const trajectory = await trajectoryFromPDB(parsed.result).run()
  return Structure.ofModel(trajectory.representative)
}

describe('author residue insertion codes', () => {
  it('keeps plain and inserted residue requests distinct', () => {
    expect(parseResidueSelection('A:52 A:52A A:52A')).toEqual([
      { chainId: 'A', seq: 52 }, { chainId: 'A', seq: 52, insertionCode: 'A' },
    ])
    expect(parseHotspotResidue('A:ARG52A')).toMatchObject({ chainId: 'A', seq: 52, insertionCode: 'A' })
  })

  it('selects only the requested residue in a real Mol* model', async () => {
    const structure = await fixture()
    for (const [insertionCode, expectedName] of [['', 'LYS'], ['A', 'ARG']]) {
      const selected = Script.getStructureSelection(buildResidueQuery([{ chainId: 'A', seq: 52, insertionCode }]), structure)
      const loci = StructureSelection.toLociWithSourceUnits(selected)
      const location = StructureElement.Loci.getFirstLocation(loci)!
      expect(StructureElement.Loci.size(loci)).toBe(1)
      expect(StructureProperties.atom.label_comp_id(location)).toBe(expectedName)
    }
  })

  it('preserves inserted residues when copying the observed sequence', async () => {
    const structure = await fixture()
    const plugin = { managers: { structure: { hierarchy: { current: { structures: [{ cell: { obj: { data: structure } } }] } } } } } as unknown as PluginContext
    expect(extractChainSequences(plugin)).toEqual([{ chainId: 'A', sequence: 'KR', residueCount: 2 }])
  })

  it('focuses and picks an inserted residue without changing its identity', async () => {
    const structure = await fixture()
    const setFromLoci = vi.fn(), focusLoci = vi.fn(), onPick = vi.fn(), unsubscribe = vi.fn()
    let click: (event: unknown) => void = () => {}
    const plugin = {
      managers: { structure: { hierarchy: { current: { structures: [{ cell: { obj: { data: structure } } }] } }, focus: { setFromLoci } }, camera: { focusLoci } },
      behaviors: { interaction: { click: { subscribe: (callback: typeof click) => { click = callback; return { unsubscribe } } } } },
    } as unknown as PluginContext
    expect(focusResidueById(plugin, 'A', 52, 'A')).toBe(true)
    const stop = subscribeResiduePicks(plugin, onPick)
    click({ current: { loci: setFromLoci.mock.calls[0][0] } })
    expect(onPick).toHaveBeenCalledWith({ chainId: 'A', seq: 52, insertionCode: 'A', label: 'A52A ARG' })
    stop()
    expect(unsubscribe).toHaveBeenCalledOnce()
  })
})
