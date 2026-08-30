import type { PluginContext } from 'molstar/lib/mol-plugin/context'
import type { StructureRepresentationBuiltInProps } from 'molstar/lib/mol-plugin-state/helpers/structure-representation-params'
import { MolScriptBuilder as MS } from 'molstar/lib/mol-script/language/builder'
import { Script } from 'molstar/lib/mol-script/script'
import { StructureSelection } from 'molstar/lib/mol-model/structure'
import { Color } from 'molstar/lib/mol-util/color'
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
  const lower = name.toLowerCase()
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
    const selection = selectedChain ? buildChainSelection(cell.obj?.data, selectedChain) : undefined
    await plugin.builders.structure.representation.addRepresentation(cell, {
      type: reprType,
      color: colorType,
      typeParams: {},
      ...(selection ? { selection } : {}),
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
): Promise<void> {
  if (!residues.length) return

  const hierarchy = plugin.managers.structure.hierarchy.current
  if (!hierarchy.structures.length) return

  const structure = hierarchy.structures[0]
  const structureData = structure.cell?.obj?.data
  if (!structureData) return

  const selection = buildResidueSelection(structureData, residues)
  if (!selection || StructureSelection.isEmpty(selection)) return

  await plugin.builders.structure.representation.addRepresentation(structure.cell, {
    type: 'ball-and-stick',
    color: 'uniform',
    colorParams: { value: Color(0xff6600) },
    typeParams: { alpha: 1 },
    selection,
  })
}

function buildChainSelection(structureData: unknown, chainId: string) {
  if (!structureData) return undefined
  const query = MS.struct.generator.atomGroups({
    'chain-test': MS.core.rel.eq([MS.ammp('auth_asym_id'), chainId]),
  })
  return Script.getStructureSelection(query, structureData as Parameters<typeof Script.getStructureSelection>[1])
}

function buildResidueSelection(structureData: unknown, residues: HighlightedResidue[]) {
  if (!residues.length) return undefined

  let query = MS.struct.generator.atomGroups({
    'chain-test': MS.core.rel.eq([MS.ammp('auth_asym_id'), residues[0].chainId]),
    'residue-test': MS.core.rel.eq([MS.ammp('auth_seq_id'), residues[0].seq]),
  })

  for (let index = 1; index < residues.length; index += 1) {
    const residue = residues[index]
    const nextQuery = MS.struct.generator.atomGroups({
      'chain-test': MS.core.rel.eq([MS.ammp('auth_asym_id'), residue.chainId]),
      'residue-test': MS.core.rel.eq([MS.ammp('auth_seq_id'), residue.seq]),
    })
    query = MS.struct.combinator.merge([query, nextQuery])
  }

  return Script.getStructureSelection(
    query,
    structureData as Parameters<typeof Script.getStructureSelection>[1],
  )
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
  await viewer.loadStructureFromData(text, structureFormatFromName(filename), {
    dataLabel: filename,
  })
}
