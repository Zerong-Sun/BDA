import { describe, expect, it } from 'vitest'
import type { ParameterFieldDefinition } from '../../lib/forms/parameterSchema'
import { hotspotConstrainedParameters, parameterOrigin } from './parameterOrigin'

/**
 * The last link in the chain: a confirmed set becomes the value a design job
 * runs against.
 *
 * Two properties matter and both are about authority. Nothing is pinned
 * without a confirmed set, because badging an operator's proposal as a
 * constraint would put a person's signature on a draft. And what is pinned is
 * `constrained` rather than `recommended`, because editing it here would
 * desynchronise the job from the record of what it was meant to target.
 */

const field = (key: string): ParameterFieldDefinition =>
  ({ key, label: key, type: 'string', default: '' }) as ParameterFieldDefinition

const FIELDS = [field('ppi.hotspot_res'), field('target_hotspot_residues'), field('num_designs')]

describe('hotspotConstrainedParameters', () => {
  it('pins the residues on the fields that take them, whatever the plugin calls it', () => {
    const pinned = hotspotConstrainedParameters('A164,A168,A171', FIELDS)

    expect(pinned).toEqual({
      'ppi.hotspot_res': 'A164,A168,A171',
      target_hotspot_residues: 'A164,A168,A171',
    })
  })

  it('pins nothing when no set has been confirmed', () => {
    expect(hotspotConstrainedParameters(undefined, FIELDS)).toEqual({})
    expect(hotspotConstrainedParameters('', FIELDS)).toEqual({})
  })

  it('touches no field that is not about residues', () => {
    expect(hotspotConstrainedParameters('A164', FIELDS)['num_designs']).toBeUndefined()
  })

  it('reads as constrained in the form, not as a suggestion', () => {
    const pinned = hotspotConstrainedParameters('A164', FIELDS)

    expect(parameterOrigin(FIELDS[0], 'A164', { constrained: pinned })).toBe('constrained')
    // Even if somebody types the same value, the fact that matters is that it
    // is pinned by a decision elsewhere.
    expect(parameterOrigin(FIELDS[0], 'A999', { constrained: pinned })).toBe('constrained')
    expect(parameterOrigin(FIELDS[2], '8', { constrained: pinned })).toBe('edited')
  })
})
