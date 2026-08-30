import type { PluginContext } from 'molstar/lib/mol-plugin/context'
import { describe, expect, it } from 'vitest'
import { enumerateChainsFromPlugin, structureFormatFromName } from './structureLoader'

describe('structureFormatFromName', () => {
  it('detects mmcif extensions', () => {
    expect(structureFormatFromName('model.cif')).toBe('mmcif')
    expect(structureFormatFromName('model.mmcif')).toBe('mmcif')
  })

  it('defaults to pdb', () => {
    expect(structureFormatFromName('model.pdb')).toBe('pdb')
    expect(structureFormatFromName('download')).toBe('pdb')
  })
})

describe('enumerateChainsFromPlugin', () => {
  it('reads chain indices from Molstar chain atom segments', () => {
    const plugin = {
      managers: {
        structure: {
          hierarchy: {
            current: {
              structures: [{
                cell: {
                  obj: {
                    data: {
                      units: [{
                        elements: [0],
                        model: {
                          atomicHierarchy: {
                            chainAtomSegments: { index: [1] },
                            chains: { auth_asym_id: { value: (index: number) => index === 1 ? 'B' : 'A' } },
                          },
                        },
                      }],
                    },
                  },
                },
              }],
            },
          },
        },
      },
    } as unknown as PluginContext

    expect(enumerateChainsFromPlugin(plugin)).toEqual(['B'])
  })
})
