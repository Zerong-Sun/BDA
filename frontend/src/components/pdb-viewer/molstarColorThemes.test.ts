import { describe, expect, it, vi } from 'vitest'
import type { PluginContext } from 'molstar/lib/mol-plugin/context'
import {
  PLDDT_THEME_NAME,
  PlddtColorThemeProvider,
  RESIDUE_CLASS_THEME_NAME,
  ResidueClassColorThemeProvider,
  registerBdaColorThemes,
  residueClassColor,
} from './molstarColorThemes'
import { molstarColorTheme } from './ColorPresets'

describe('residueClassColor', () => {
  it('separates positive, negative, hydrophobic and neutral residues', () => {
    const positive = residueClassColor('ARG')
    const negative = residueClassColor('GLU')
    const hydrophobic = residueClassColor('LEU')
    const other = residueClassColor('SER')

    expect(new Set([positive, negative, hydrophobic, other]).size).toBe(4)
    expect(residueClassColor('lys')).toBe(positive)
    expect(residueClassColor('HIP')).toBe(positive)
    expect(residueClassColor('ASP')).toBe(negative)
    expect(residueClassColor('TRP')).toBe(hydrophobic)
    // Glycine has no side chain to highlight, and unknown residues stay neutral.
    expect(residueClassColor('GLY')).toBe(other)
    expect(residueClassColor('UNK')).toBe(other)
  })
})

describe('registerBdaColorThemes', () => {
  function pluginWithRegistry(registered: string[]) {
    const add = vi.fn((provider: { name: string }) => registered.push(provider.name))
    const has = vi.fn((provider: { name: string }) => registered.includes(provider.name))
    return {
      plugin: {
        representation: { structure: { themes: { colorThemeRegistry: { add, has } } } },
      } as unknown as PluginContext,
      add,
    }
  }

  it('registers both presets exactly once per plugin', () => {
    const registered: string[] = []
    const { plugin, add } = pluginWithRegistry(registered)

    registerBdaColorThemes(plugin)
    registerBdaColorThemes(plugin)

    expect(add).toHaveBeenCalledTimes(2)
    expect(registered).toEqual([PLDDT_THEME_NAME, RESIDUE_CLASS_THEME_NAME])
  })
})

describe('color preset wiring', () => {
  it('maps the new presets to the registered theme names', () => {
    expect(molstarColorTheme('plddt')).toBe(PlddtColorThemeProvider.name)
    expect(molstarColorTheme('charge-hydrophobic')).toBe(ResidueClassColorThemeProvider.name)
  })
})
