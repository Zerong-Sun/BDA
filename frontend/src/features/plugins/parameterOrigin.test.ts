import { describe, expect, it } from 'vitest'
import type { ParameterFieldDefinition } from '../../lib/forms/parameterSchema'
import { clusterConstrainedParameters, parameterOrigin } from './parameterOrigin'

/**
 * Whose value is this?
 *
 * The form used to show a plugin default, a proposed value and something you typed
 * identically. That is the cheapest half of agent transparency to provide - one word per
 * field, not a rationale - and the half that changes whether someone overrides a value.
 */

function field(key: string, fallback: unknown = undefined): ParameterFieldDefinition {
  return { key, type: 'number', label: key, default: fallback } as ParameterFieldDefinition
}

describe('parameterOrigin', () => {
  it('says nothing about an untouched default', () => {
    expect(parameterOrigin(field('seeds', 3), 3)).toBe('default')
  })

  it('marks a value proposed for this run', () => {
    expect(parameterOrigin(field('seeds', 3), 8, { recommended: { seeds: 8 } })).toBe('recommended')
  })

  it('marks a value the editor chose over everything on offer', () => {
    expect(parameterOrigin(field('seeds', 3), 11, { recommended: { seeds: 8 } })).toBe('edited')
  })

  it('reports a constraint even when the pinned value equals the default', () => {
    // The fact that changes what the reader should do is that it is pinned, not that it
    // happens to coincide with the default.
    expect(parameterOrigin(field('cpus', 4), 4, { constrained: { cpus: 4 } })).toBe('constrained')
  })

  it('treats a structurally equal value as the same value', () => {
    const listy = field('chains', ['A', 'B'])
    expect(parameterOrigin(listy, ['A', 'B'])).toBe('default')
  })
})

describe('clusterConstrainedParameters', () => {
  it('pins the thread count a plugin declared slots for', () => {
    // -n, span[ptile] and the tool's thread count come from one number; letting one drift
    // here is the mismatch the project treats as a violation rather than a notice.
    const pinned = clusterConstrainedParameters({ cpus: 8 }, [field('n_cpu'), field('seeds')])
    expect(pinned).toEqual({ n_cpu: 8 })
  })

  it('pins nothing when the plugin declared nothing', () => {
    // A badge on a field nobody is bound by is how a transparency signal stops being read.
    expect(clusterConstrainedParameters({}, [field('n_cpu')])).toEqual({})
    expect(clusterConstrainedParameters(undefined, [field('n_cpu')])).toEqual({})
  })

  it('ignores a declaration that is not a positive slot count', () => {
    expect(clusterConstrainedParameters({ cpus: 0 }, [field('threads')])).toEqual({})
    expect(clusterConstrainedParameters({ cpus: 'lots' }, [field('threads')])).toEqual({})
  })
})
