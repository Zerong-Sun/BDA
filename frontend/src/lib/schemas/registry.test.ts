import { describe, expect, it } from 'vitest'
import { ModelPluginSchema } from './registry'

describe('ModelPluginSchema', () => {
  it('retains declaration and runtime-validation state from the registry response', () => {
    const plugin = ModelPluginSchema.parse({
      id: 'plugin-mpnn',
      plugin_key: 'ProteinMPNN',
      plugin_version: '1.0.1',
      name: 'ProteinMPNN',
      container_image: '/work/mpnn',
      command: 'run',
      parameter_schema: {},
      output_schema: {},
      enabled: true,
      validation_status: 'valid',
      validated_at: '2026-08-30T00:00:00Z',
      validation_errors: [],
      runtime_validation_status: 'failed',
      runtime_validated_at: '2026-08-30T00:01:00Z',
      runtime_validation_evidence: {
        declaration_fingerprint: 'sha256:proof',
        checks: ['output port collected'],
      },
      version: 4,
      created_at: '2026-08-29T00:00:00Z',
      updated_at: '2026-08-30T00:01:00Z',
    })

    expect(plugin.validation_status).toBe('valid')
    expect(plugin.runtime_validation_status).toBe('failed')
    expect(plugin.runtime_validated_at).toBe('2026-08-30T00:01:00Z')
    expect(plugin.runtime_validation_evidence).toEqual({
      declaration_fingerprint: 'sha256:proof',
      checks: ['output port collected'],
    })
  })
})
