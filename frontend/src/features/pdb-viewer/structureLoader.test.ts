import type { PluginContext } from 'molstar/lib/mol-plugin/context'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { applyVisualPreset, enumerateChainsFromPlugin, loadStructureFromAuthenticatedUrl, structureFormatFromName } from './structureLoader'

describe('switching the displayed structure preset', () => {
  it('replaces the previous scene instead of retaining its cartoon and colors', async () => {
    const root = { obj: { data: {} } }
    const scene: Array<{ parent: unknown; type: string; color: string }> = []
    const components = new Set<unknown>()
    const plugin = {
      managers: { structure: { hierarchy: { current: { structures: [{ cell: root }] } }, component: {
        clear: async () => { for (let i = scene.length - 1; i >= 0; i--) if (components.has(scene[i].parent)) scene.splice(i, 1); components.clear() },
      } } },
      builders: { structure: {
        tryCreateComponentStatic: async () => { const component = {}; components.add(component); return component },
        representation: { addRepresentation: async (parent: unknown, props: { type: string; color: string }) => { scene.push({ parent, ...props }) } },
      } },
    } as unknown as PluginContext
    await applyVisualPreset(plugin, 'cartoon', 'chain-id')
    await applyVisualPreset(plugin, 'ball-and-stick', 'hydrophobicity')
    expect(scene).toHaveLength(1)
    expect(scene[0]).toMatchObject({ type: 'ball-and-stick', color: 'hydrophobicity' })
    expect(scene[0].parent).not.toBe(root)
  })
})

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
