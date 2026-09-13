import type { PluginContext } from 'molstar/lib/mol-plugin/context'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { enumerateChainsFromPlugin, loadStructureFromAuthenticatedUrl, structureFormatFromName } from './structureLoader'

describe('structureFormatFromName', () => {
  it('detects mmcif extensions', () => {
    expect(structureFormatFromName('model.cif')).toBe('mmcif')
    expect(structureFormatFromName('model.mmcif')).toBe('mmcif')
    expect(structureFormatFromName('https://storage.test/model.cif?signature=example')).toBe('mmcif')
  })

  it('defaults to pdb', () => {
    expect(structureFormatFromName('model.pdb')).toBe('pdb')
    expect(structureFormatFromName('download')).toBe('pdb')
  })
})

describe('loadStructureFromAuthenticatedUrl', () => {
  afterEach(() => vi.unstubAllGlobals())

  it.each([
    ['chemical/x-mmcif', 'data_reference\n#\nloop_\n_atom_site.id\n1\n'],
    ['application/octet-stream', '# deposited structure\ndata_reference\n_atom_site.id 1\n'],
  ])('loads mmCIF from an opaque storage key with %s', async (contentType, body) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      headers: { 'content-type': contentType },
    })))
    const viewer = { loadStructureFromData: vi.fn().mockResolvedValue(undefined) }
    await loadStructureFromAuthenticatedUrl(viewer, 'https://storage.test/artifacts/opaque?signature=example')
    expect(viewer.loadStructureFromData).toHaveBeenCalledWith(body, 'mmcif', expect.any(Object))
  })

  it('retains PDB parsing for an opaque PDB upload', async () => {
    const body = 'HEADER    REFERENCE\nATOM      1  N   ALA A   1\n'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      headers: { 'content-type': 'chemical/x-pdb' },
    })))
    const viewer = { loadStructureFromData: vi.fn().mockResolvedValue(undefined) }
    await loadStructureFromAuthenticatedUrl(viewer, 'https://storage.test/artifacts/opaque')
    expect(viewer.loadStructureFromData).toHaveBeenCalledWith(body, 'pdb', expect.any(Object))
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
