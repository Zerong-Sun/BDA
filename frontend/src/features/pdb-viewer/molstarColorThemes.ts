import type { Location } from 'molstar/lib/mol-model/location'
import {
  Bond,
  StructureElement,
  StructureProperties,
  Unit,
  type Structure,
} from 'molstar/lib/mol-model/structure'
import type { PluginContext } from 'molstar/lib/mol-plugin/context'
import type { ColorTheme } from 'molstar/lib/mol-theme/color'
import { ColorThemeCategory } from 'molstar/lib/mol-theme/color/categories'
import type { ThemeDataContext } from 'molstar/lib/mol-theme/theme'
import { Color, ColorScale } from 'molstar/lib/mol-util/color'
import { TableLegend } from 'molstar/lib/mol-util/legend'
import { ParamDefinition as PD } from 'molstar/lib/mol-util/param-definition'

import { PLDDT_THEME_NAME, RESIDUE_CLASS_THEME_NAME } from './molstarColorThemeNames'

export { PLDDT_THEME_NAME, RESIDUE_CLASS_THEME_NAME }

const NO_DATA_COLOR = Color(0xa0a0a0)

/**
 * Red (low confidence) to green (high confidence). AlphaFold's own palette is
 * orange/blue, but the wet-lab reviewers here read red/green as bad/good, so the
 * scale follows that convention instead.
 */
const PLDDT_COLORS = [
  Color(0xd7191c),
  Color(0xfdae61),
  Color(0xffd966),
  Color(0xa6d96a),
  Color(0x1a9641),
]
const PLDDT_DOMAIN: [number, number] = [50, 95]

const PLDDT_LEGEND = TableLegend([
  ['≤ 50 very low', PLDDT_COLORS[0]],
  ['70 low', PLDDT_COLORS[1]],
  ['80 medium', PLDDT_COLORS[2]],
  ['90 high', PLDDT_COLORS[3]],
  ['≥ 95 very high', PLDDT_COLORS[4]],
])

/**
 * pLDDT lives in the B-factor column of AlphaFold/Boltz outputs, but some
 * writers emit it as a 0-1 fraction. Sampling a few atoms tells the two apart
 * without walking every atom of a large complex.
 */
const PLDDT_FRACTION_SAMPLE_SIZE = 512

function readBFactor(unit: Unit, element: StructureElement.UnitIndex | number): number {
  if (Unit.isAtomic(unit)) {
    return unit.model.atomicConformation.B_iso_or_equiv.value(element as number)
  }
  return Number.NaN
}

export function plddtIsFraction(structure: Structure | undefined): boolean {
  if (!structure) return false
  let seen = 0
  let max = 0
  for (const unit of structure.units) {
    if (!Unit.isAtomic(unit)) continue
    const { elements } = unit
    for (let index = 0; index < elements.length; index += 1) {
      const value = readBFactor(unit, elements[index])
      if (!Number.isFinite(value)) continue
      if (value > max) max = value
      seen += 1
      if (seen >= PLDDT_FRACTION_SAMPLE_SIZE) break
    }
    if (seen >= PLDDT_FRACTION_SAMPLE_SIZE) break
  }
  return seen > 0 && max > 0 && max <= 1
}

export const PlddtColorThemeParams = {}
export type PlddtColorThemeParams = typeof PlddtColorThemeParams

export function PlddtColorTheme(
  ctx: ThemeDataContext,
  props: PD.Values<PlddtColorThemeParams>,
): ColorTheme<PlddtColorThemeParams> {
  const scale = ColorScale.create({ domain: PLDDT_DOMAIN, listOrName: PLDDT_COLORS })
  const fraction = plddtIsFraction(ctx.structure)

  function scoreColor(unit: Unit, element: number): Color {
    const raw = readBFactor(unit, element)
    if (!Number.isFinite(raw) || raw < 0) return NO_DATA_COLOR
    return scale.color(fraction ? raw * 100 : raw)
  }

  function color(location: Location): Color {
    if (StructureElement.Location.is(location)) {
      return scoreColor(location.unit, location.element)
    }
    if (Bond.isLocation(location)) {
      return scoreColor(location.aUnit, location.aUnit.elements[location.aIndex])
    }
    return NO_DATA_COLOR
  }

  return {
    factory: PlddtColorTheme,
    granularity: 'group',
    preferSmoothing: true,
    color,
    props,
    description:
      'Colors each atom by its B-factor column, which AlphaFold-style predictors use to store pLDDT: red is low confidence, green is high.',
    legend: PLDDT_LEGEND,
  }
}

export const PlddtColorThemeProvider: ColorTheme.Provider<PlddtColorThemeParams, typeof PLDDT_THEME_NAME> = {
  name: PLDDT_THEME_NAME,
  label: 'pLDDT (red → green)',
  category: ColorThemeCategory.Validation,
  factory: PlddtColorTheme,
  getParams: () => PlddtColorThemeParams,
  defaultValues: PD.getDefaultValues(PlddtColorThemeParams),
  isApplicable: (ctx: ThemeDataContext) => !!ctx.structure,
}

const BACKBONE_COLOR = Color(0xf5f5f5)
const POSITIVE_COLOR = Color(0x2b6cb0)
const NEGATIVE_COLOR = Color(0xc53030)
const HYDROPHOBIC_COLOR = Color(0xdd8b20)

const POSITIVE_RESIDUES = new Set(['ARG', 'LYS', 'HIS', 'HIP', 'HSP'])
const NEGATIVE_RESIDUES = new Set(['ASP', 'GLU', 'ASH', 'GLH'])
const HYDROPHOBIC_RESIDUES = new Set(['ALA', 'VAL', 'LEU', 'ILE', 'MET', 'PHE', 'TRP', 'PRO'])

const RESIDUE_CLASS_LEGEND = TableLegend([
  ['Positive (R/K/H)', POSITIVE_COLOR],
  ['Negative (D/E)', NEGATIVE_COLOR],
  ['Hydrophobic (A/V/L/I/M/F/W/P)', HYDROPHOBIC_COLOR],
  ['Other', BACKBONE_COLOR],
])

export function residueClassColor(compId: string): Color {
  const name = compId.toUpperCase()
  if (POSITIVE_RESIDUES.has(name)) return POSITIVE_COLOR
  if (NEGATIVE_RESIDUES.has(name)) return NEGATIVE_COLOR
  if (HYDROPHOBIC_RESIDUES.has(name)) return HYDROPHOBIC_COLOR
  return BACKBONE_COLOR
}

export const ResidueClassColorThemeParams = {}
export type ResidueClassColorThemeParams = typeof ResidueClassColorThemeParams

export function ResidueClassColorTheme(
  ctx: ThemeDataContext,
  props: PD.Values<ResidueClassColorThemeParams>,
): ColorTheme<ResidueClassColorThemeParams> {
  let color: (location: Location) => Color = () => BACKBONE_COLOR

  if (ctx.structure) {
    const probe = StructureElement.Location.create(ctx.structure.root)
    const locationColor = (location: StructureElement.Location) => {
      if (!Unit.isAtomic(location.unit)) return BACKBONE_COLOR
      return residueClassColor(StructureProperties.atom.label_comp_id(location))
    }
    color = (location: Location) => {
      if (StructureElement.Location.is(location)) return locationColor(location)
      if (Bond.isLocation(location)) {
        probe.unit = location.aUnit
        probe.element = location.aUnit.elements[location.aIndex]
        return locationColor(probe)
      }
      return BACKBONE_COLOR
    }
  }

  return {
    factory: ResidueClassColorTheme,
    granularity: 'group',
    color,
    props,
    description:
      'Keeps the backbone white and highlights charged and hydrophobic side chains, so surface patches stand out at a glance.',
    legend: RESIDUE_CLASS_LEGEND,
  }
}

export const ResidueClassColorThemeProvider: ColorTheme.Provider<
  ResidueClassColorThemeParams,
  typeof RESIDUE_CLASS_THEME_NAME
> = {
  name: RESIDUE_CLASS_THEME_NAME,
  label: 'Charge & hydrophobicity',
  category: ColorThemeCategory.Residue,
  factory: ResidueClassColorTheme,
  getParams: () => ResidueClassColorThemeParams,
  defaultValues: PD.getDefaultValues(ResidueClassColorThemeParams),
  isApplicable: (ctx: ThemeDataContext) => !!ctx.structure,
}

/** Registering twice throws inside Mol*, and every viewer instance calls this. */
export function registerBdaColorThemes(plugin: PluginContext): void {
  const registry = plugin.representation.structure.themes.colorThemeRegistry
  for (const provider of [PlddtColorThemeProvider, ResidueClassColorThemeProvider]) {
    if (registry.has(provider)) continue
    registry.add(provider)
  }
}
