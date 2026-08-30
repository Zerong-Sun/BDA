import type { TranslationDict } from '../../lib/i18n/types'
import { PLDDT_THEME_NAME, RESIDUE_CLASS_THEME_NAME } from './molstarColorThemeNames'

export type RepresentationPreset =
  | 'cartoon'
  | 'surface'
  | 'ball-and-stick'
  | 'backbone'

export type ColorPreset =
  | 'chain-id'
  | 'hydrophobicity'
  | 'electrostatics'
  | 'secondary-structure'
  | 'b-factor'
  | 'plddt'
  | 'charge-hydrophobic'

export type ViewPreset = 'front' | 'back' | 'top' | 'bottom' | 'side' | 'focus'

type ViewerLabels = TranslationDict['viewer']

export function getRepresentationOptions(v: ViewerLabels): { id: RepresentationPreset; label: string }[] {
  return [
    { id: 'cartoon', label: v.representationCartoon },
    { id: 'surface', label: v.representationSurface },
    { id: 'ball-and-stick', label: v.representationBallStick },
    { id: 'backbone', label: v.representationBackbone },
  ]
}

export function getColorOptions(v: ViewerLabels): { id: ColorPreset; label: string; description: string }[] {
  return [
    { id: 'chain-id', label: v.colorChain, description: v.colorChainDesc },
    { id: 'hydrophobicity', label: v.colorHydrophobicity, description: v.colorHydrophobicityDesc },
    { id: 'electrostatics', label: v.colorElectrostatics, description: v.colorElectrostaticsDesc },
    { id: 'secondary-structure', label: v.colorSecondaryStructure, description: v.colorSecondaryStructureDesc },
    { id: 'b-factor', label: v.colorBFactor, description: v.colorBFactorDesc },
    { id: 'plddt', label: v.colorPlddt, description: v.colorPlddtDesc },
    {
      id: 'charge-hydrophobic',
      label: v.colorChargeHydrophobic,
      description: v.colorChargeHydrophobicDesc,
    },
  ]
}

export function getViewOptions(v: ViewerLabels): { id: ViewPreset; label: string }[] {
  return [
    { id: 'front', label: v.viewFront },
    { id: 'back', label: v.viewBack },
    { id: 'top', label: v.viewTop },
    { id: 'bottom', label: v.viewBottom },
    { id: 'side', label: v.viewSide },
    { id: 'focus', label: v.viewFocus },
  ]
}

export function molstarRepresentation(type: RepresentationPreset): string {
  switch (type) {
    case 'cartoon':
      return 'cartoon'
    case 'surface':
      return 'molecular-surface'
    case 'ball-and-stick':
      return 'ball-and-stick'
    case 'backbone':
      return 'backbone'
    default:
      return 'cartoon'
  }
}

export function molstarColorTheme(type: ColorPreset): string {
  switch (type) {
    case 'chain-id':
      return 'chain-id'
    case 'hydrophobicity':
      return 'hydrophobicity'
    case 'electrostatics':
      return 'residue-charge'
    case 'secondary-structure':
      return 'secondary-structure'
    case 'b-factor':
      return 'uncertainty'
    case 'plddt':
      return PLDDT_THEME_NAME
    case 'charge-hydrophobic':
      return RESIDUE_CLASS_THEME_NAME
    default:
      return 'chain-id'
  }
}
