import type { PluginContext } from 'molstar/lib/mol-plugin/context'
import type { StructureRepresentationBuiltInProps } from 'molstar/lib/mol-plugin-state/helpers/structure-representation-params'
import { MolScriptBuilder as MS } from 'molstar/lib/mol-script/language/builder'
import { Script } from 'molstar/lib/mol-script/script'
import { StructureElement, StructureProperties, StructureSelection } from 'molstar/lib/mol-model/structure'
import { Color } from 'molstar/lib/mol-util/color'
import { ProteinBackboneAtoms } from 'molstar/lib/mol-model/structure/model/types'
import { SetUtils } from 'molstar/lib/mol-util/set'
import { OrderedSet } from 'molstar/lib/mol-data/int'
import { apiAuthorizationHeaders } from '../../lib/api/client'
import {
  type ColorPreset,
  type RepresentationPreset,
  molstarColorTheme,
  molstarRepresentation,
} from './ColorPresets'
import type { HighlightedResidue } from './types'

export type StructureFormat = 'pdb' | 'mmcif'

export function structureFormatFromName(name: string): StructureFormat {
  const lower = name.split(/[?#]/, 1)[0].toLowerCase()
  return lower.endsWith('.cif') || lower.endsWith('.mmcif') ? 'mmcif' : 'pdb'
}

export async function clearStructures(plugin: PluginContext): Promise<void> {
  const { trajectories } = plugin.managers.structure.hierarchy.current
  if (trajectories.length > 0) {
    await plugin.managers.structure.hierarchy.remove(trajectories)
  }
}

export function hasLoadedStructure(plugin: PluginContext): boolean {
  return plugin.managers.structure.hierarchy.current.structures.length > 0
}

export function enumerateChainsFromPlugin(plugin: PluginContext): string[] {
  const chainIds = new Set<string>()
  const hierarchy = plugin.managers.structure.hierarchy.current

  for (const structure of hierarchy.structures) {
    const data = structure.cell?.obj?.data
    if (!data) continue

    for (const unit of data.units) {
      if (!unit.model?.atomicHierarchy) continue
      const atomicHierarchy = unit.model.atomicHierarchy as unknown as {
        chainAtomSegments: { index: Int32Array | number[] }
        chains: {
        auth_asym_id: { value: (index: number) => string }
        }
      }
      const elements = unit.elements
      if (elements.length === 0) continue
      const chainIndex = atomicHierarchy.chainAtomSegments.index[elements[0]]
      const chainId = atomicHierarchy.chains.auth_asym_id.value(chainIndex)
      if (chainId) chainIds.add(chainId)
    }
  }

  return Array.from(chainIds).sort()
}

export async function applyVisualPreset(
  plugin: PluginContext,
  representation: RepresentationPreset,
  color: ColorPreset,
  selectedChain: string | null = null,
): Promise<void> {
  const hierarchy = plugin.managers.structure.hierarchy.current
  if (!hierarchy.structures.length) {
    console.warn('[BDA] applyVisualPreset: no structures loaded')
    return
  }

  const reprType = molstarRepresentation(representation) as StructureRepresentationBuiltInProps['type']
  const colorType = molstarColorTheme(color) as StructureRepresentationBuiltInProps['color']

  const snapshot = hierarchy.structures.map((structure) => ({
    cell: structure.cell,
  }))

  await plugin.managers.structure.component.clear(hierarchy.structures)

  for (const { cell } of snapshot) {
    // Representations must belong to a component. Root representations are not
    // removed by component.clear, so switching presets used to stack old views.
    const component = selectedChain
      ? await plugin.builders.structure.tryCreateComponentFromExpression(cell, MS.struct.generator.atomGroups({
        'chain-test': MS.core.rel.eq([MS.ammp('auth_asym_id'), selectedChain]),
      }), 'bda-view', { label: `Chain ${selectedChain}` })
      : await plugin.builders.structure.tryCreateComponentStatic(cell, 'all', { label: 'Structure' })
    if (!component) continue
    await plugin.builders.structure.representation.addRepresentation(component, {
      type: reprType,
      color: colorType,
      typeParams: {},
    })
  }
}

export async function applyChainFilter(
  plugin: PluginContext,
  representation: RepresentationPreset,
  color: ColorPreset,
  selectedChain: string | null,
): Promise<void> {
  await applyVisualPreset(plugin, representation, color, selectedChain)
}

export async function resetCamera(plugin: PluginContext): Promise<void> {
  const camera = plugin.managers.camera as PluginContext['managers']['camera'] & {
    reset?: () => void
  }
  if (typeof camera.reset === 'function') {
    camera.reset()
  }
  plugin.managers.camera.focusObject({ durationMs: 250 })
}

export async function applyResidueHighlights(
  plugin: PluginContext,
  residues: HighlightedResidue[],
  options: { sideChainsOnly?: boolean; focus?: boolean; labels?: boolean } = {},
): Promise<{ residues: HighlightedResidue[]; atomCount: number } | undefined> {

  const hierarchy = plugin.managers.structure.hierarchy.current
  if (!hierarchy.structures.length) return

  const structure = hierarchy.structures[0]
  const structureData = structure.cell?.obj?.data
  if (!structureData) return

  const old = (structure.components ?? []).filter(component => component.cell.transform.tags?.includes('structure-component-bda-residue-highlight'))
  if (old.length) await plugin.managers.structure.hierarchy.remove(old)
  if (!residues.length) return

  const component = await plugin.builders.structure.tryCreateComponentFromExpression(
    structure.cell, buildResidueQuery(residues, options.sideChainsOnly), 'bda-residue-highlight', { label: options.sideChainsOnly ? 'Selected side chains' : 'Selected residues' },
  )
  if (!component) return

  await plugin.builders.structure.representation.addRepresentation(component, {
    type: 'ball-and-stick',
    color: 'uniform',
    colorParams: { value: Color(0xe83e9b) },
    typeParams: { alpha: 1, sizeFactor: 0.35 },
  })
  const data = component.cell?.obj?.data
  if (!data) return
  const found = new Map<string, HighlightedResidue>()
  for (const unit of data.units) for (let index = 0; index < OrderedSet.size(unit.elements); index++) {
    const element = OrderedSet.getAt(unit.elements, index)
    const location = StructureElement.Location.create(data, unit, element)
    const chainId = StructureProperties.chain.auth_asym_id(location)
    const seq = StructureProperties.residue.auth_seq_id(location)
    const name = StructureProperties.atom.label_comp_id(location)
    found.set(`${chainId}:${seq}`, { chainId, seq, label: `${chainId}:${seq} ${name}` })
  }
  // A single 3D label is legible. Clustered selections use the residue list in
  // the controls so overlapping labels cannot cover the highlighted side chains.
  if (options.labels && found.size === 1) await plugin.builders.structure.representation.addRepresentation(component, {
    type: 'label', color: 'uniform', colorParams: { value: Color(0x273026) },
    typeParams: { level: 'residue', background: true, backgroundColor: Color(0xffffff), backgroundOpacity: 0.85, sizeFactor: 1.4, offsetZ: 12, attachment: 'bottom-left' },
  })
  if (options.focus) plugin.managers.camera.focusObject({ targets: [{ targetRef: component.ref, extraRadius: 12 }], minRadius: 12, durationMs: 250 })
  return { residues: [...found.values()], atomCount: data.elementCount }
}

function buildResidueQuery(residues: HighlightedResidue[], sideChainsOnly = false) {
  const atomTest = sideChainsOnly ? MS.core.logic.not([MS.core.set.has([MS.set(...SetUtils.toArray(ProteinBackboneAtoms)), MS.ammp('label_atom_id')])]) : undefined
  let query = MS.struct.generator.atomGroups({
    'chain-test': MS.core.rel.eq([MS.ammp('auth_asym_id'), residues[0].chainId]),
    'residue-test': MS.core.rel.eq([MS.ammp('auth_seq_id'), residues[0].seq]),
    ...(atomTest ? { 'atom-test': atomTest } : {}),
  })

  for (let index = 1; index < residues.length; index += 1) {
    const residue = residues[index]
    const nextQuery = MS.struct.generator.atomGroups({
      'chain-test': MS.core.rel.eq([MS.ammp('auth_asym_id'), residue.chainId]),
      'residue-test': MS.core.rel.eq([MS.ammp('auth_seq_id'), residue.seq]),
      ...(atomTest ? { 'atom-test': atomTest } : {}),
    })
    query = MS.struct.combinator.merge([query, nextQuery])
  }

  return query
}

export async function loadStructureFromAuthenticatedUrl(
  viewer: {
    loadStructureFromData: (
      data: string,
      format: StructureFormat,
      options?: { dataLabel?: string },
    ) => Promise<void>
  },
  url: string,
): Promise<void> {
  const response = await fetch(url, {
    headers: apiAuthorizationHeaders(url),
  })
  if (!response.ok) {
    throw new Error(`Structure download failed (${response.status})`)
  }
  const disposition = response.headers.get('content-disposition') ?? ''
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? url
  const text = await response.text()
  if (!text.trim()) {
    throw new Error('Structure file is empty')
  }
  // Uploaded artifacts have opaque object keys. Use the response's format evidence
  // before falling back to a filename, which may only be a signed storage URL.
  const contentType = (response.headers.get('content-type') ?? '').split(';', 1)[0].trim().toLowerCase()
  const format = contentType === 'chemical/x-mmcif' || contentType === 'chemical/x-cif'
    || (/^\s*(?:#[^\n]*\n\s*)*data_\S+/i.test(text) && /(?:^|\n)_atom_site\./.test(text))
    ? 'mmcif'
    : structureFormatFromName(filename)
  await viewer.loadStructureFromData(text, format, {
    dataLabel: filename,
  })
}


/**
 * Report the residue a person clicks in the viewer.
 *
 * The viewer could already be *told* which residues to highlight; it could not
 * be *asked*. That asymmetry is why picking a binding site was a sentence typed
 * into a chat box and then retyped into a parameter field.
 *
 * Residues are reported in the author numbering (`auth_asym_id` /
 * `auth_seq_id`) because that is what the viewer displays, what a person reads
 * off a paper, and what the design tools take on their command lines. Using the
 * canonical numbering here would silently move every residue in the files where
 * the two differ.
 *
 * Returns its own unsubscribe. A click outside the structure clears the loci
 * and is ignored rather than reported as a selection of nothing.
 */
export function subscribeResiduePicks(
  plugin: PluginContext,
  onPick: (residue: HighlightedResidue) => void,
): () => void {
  const subscription = plugin.behaviors.interaction.click.subscribe((event) => {
    const loci = event?.current?.loci
    if (!loci || !StructureElement.Loci.is(loci) || StructureElement.Loci.isEmpty(loci)) return
    const location = StructureElement.Loci.getFirstLocation(loci)
    if (!location) return
    const chainId = StructureProperties.chain.auth_asym_id(location)
    const seq = StructureProperties.residue.auth_seq_id(location)
    if (!chainId || typeof seq !== 'number') return
    const name = StructureProperties.atom.label_comp_id(location)
    onPick({ chainId, seq, label: name ? `${chainId}${seq} ${name}` : `${chainId}${seq}` })
  })
  return () => subscription.unsubscribe()
}

/** Select an existing author-numbered residue using the same Mol* focus as a canvas click. */
export function focusResidueById(plugin: PluginContext, chainId: string, seq: number): boolean {
  const structure = plugin.managers.structure.hierarchy.current.structures[0]?.cell?.obj?.data
  if (!structure) return false
  const selection = Script.getStructureSelection(buildResidueQuery([{ chainId, seq }]), structure)
  if (!selection || StructureSelection.isEmpty(selection)) return false
  const loci = StructureSelection.toLociWithSourceUnits(selection)
  plugin.managers.structure.focus.setFromLoci(loci)
  plugin.managers.camera.focusLoci(loci, { minRadius: 18, extraRadius: 8, durationMs: 250 })
  return true
}
