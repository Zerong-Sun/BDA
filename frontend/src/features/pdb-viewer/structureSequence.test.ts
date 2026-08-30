import { describe, expect, it, vi } from 'vitest'
import type { PluginContext } from 'molstar/lib/mol-plugin/context'
import {
  copyTextToClipboard,
  extractChainSequences,
  formatFasta,
} from './structureSequence'

function pluginWithoutStructure(): PluginContext {
  return {
    managers: { structure: { hierarchy: { current: { structures: [] } } } },
  } as unknown as PluginContext
}

describe('formatFasta', () => {
  it('emits one record per chain and wraps sequences at 60 columns', () => {
    const sequence = 'ACDEFGHIKL'.repeat(7)
    const fasta = formatFasta(
      [{ chainId: 'A', sequence, residueCount: sequence.length }],
      'Brazzein 4HE7',
    )
    const lines = fasta.split('\n')

    expect(lines[0]).toBe('>Brazzein_4HE7|Chain_A|70aa')
    expect(lines[1]).toHaveLength(60)
    expect(lines[2]).toBe(sequence.slice(60))
    expect(lines).toHaveLength(3)
  })

  it('keeps chains separate and falls back to a generic label', () => {
    const fasta = formatFasta([
      { chainId: 'A', sequence: 'ACD', residueCount: 3 },
      { chainId: 'B', sequence: 'EFG', residueCount: 3 },
    ], null)

    expect(fasta).toBe('>structure|Chain_A|3aa\nACD\n>structure|Chain_B|3aa\nEFG')
  })
})

describe('extractChainSequences', () => {
  it('returns nothing when no structure is loaded', () => {
    expect(extractChainSequences(pluginWithoutStructure())).toEqual([])
  })
})

describe('copyTextToClipboard', () => {
  it('uses the async clipboard when it is available', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })

    await expect(copyTextToClipboard('>a\nACD')).resolves.toBe(true)
    expect(writeText).toHaveBeenCalledWith('>a\nACD')
  })

  it('falls back to execCommand when the clipboard API rejects', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    })
    const execCommand = vi.fn(() => true)
    Object.defineProperty(document, 'execCommand', { configurable: true, value: execCommand })

    await expect(copyTextToClipboard('>a\nACD')).resolves.toBe(true)
    expect(execCommand).toHaveBeenCalledWith('copy')
    expect(document.querySelector('textarea')).toBeNull()
  })

  it('reports failure when neither path can copy', async () => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined })
    Object.defineProperty(document, 'execCommand', {
      configurable: true,
      value: vi.fn(() => false),
    })

    await expect(copyTextToClipboard('>a\nACD')).resolves.toBe(false)
  })
})
