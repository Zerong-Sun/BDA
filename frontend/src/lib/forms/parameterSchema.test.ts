import { describe, expect, it } from 'vitest'
import {
  defaultsFromFields,
  fieldsFromParameterSchema,
  parseParameterSchema,
} from './parameterSchema'

// The ProteinHunter (Boltz) registration, trimmed to the shapes that matter here: an
// enum, free text, a bounded integer, a bounded number, a boolean, and the mutually
// exclusive ligand pair. It is JSON Schema because PLUGIN_INTERFACE.md declares
// parameter_schema that way and preflight validates node parameters against it.
const PROTEINHUNTER_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  properties: {
    mode: {
      type: 'string',
      enum: ['binder', 'unconditional'],
      default: 'binder',
      description: 'Design chain A against supplied targets, or generate an unconditional protein.',
    },
    protein_seqs: { type: 'string', default: '', 'x-bda-field-type': 'textarea' },
    ligand_smiles: { type: 'string', default: '', description: 'SMILES target.' },
    ligand_ccd: { type: 'string', default: '', description: 'PDB CCD code target.' },
    num_designs: { type: 'integer', minimum: 1, maximum: 10000, default: 3 },
    temperature: { type: 'number', minimum: 0.0, maximum: 10.0, default: 1.0 },
    cyclic: { type: 'boolean', default: false },
    recycling_steps: { type: 'integer', minimum: 0, maximum: 20, default: 3, 'x-bda-advanced': true },
  },
  required: ['mode', 'num_designs'],
  not: {
    required: ['ligand_smiles', 'ligand_ccd'],
    properties: { ligand_smiles: { minLength: 1 }, ligand_ccd: { minLength: 1 } },
  },
}

describe('parseParameterSchema', () => {
  it('reads the fields shape when a plugin declares one', () => {
    const fields = parseParameterSchema({
      fields: [{ key: 'num_designs', type: 'integer', default: 5 }],
    })
    expect(fields).toEqual([{ key: 'num_designs', type: 'integer', default: 5 }])
  })

  it('derives fields from a JSON Schema plugin declaration', () => {
    const fields = parseParameterSchema(PROTEINHUNTER_SCHEMA)
    expect(fields.map((field) => field.key)).toEqual([
      'mode',
      'protein_seqs',
      'ligand_smiles',
      'ligand_ccd',
      'num_designs',
      'temperature',
      'cyclic',
      'recycling_steps',
    ])
  })

  it('maps JSON Schema types, bounds, enums and descriptions onto controls', () => {
    const byKey = Object.fromEntries(
      parseParameterSchema(PROTEINHUNTER_SCHEMA).map((field) => [field.key, field]),
    )
    expect(byKey.mode).toMatchObject({
      type: 'enum',
      options: ['binder', 'unconditional'],
      default: 'binder',
      required: true,
      help: 'Design chain A against supplied targets, or generate an unconditional protein.',
    })
    expect(byKey.num_designs).toMatchObject({ type: 'integer', min: 1, max: 10000, required: true })
    expect(byKey.temperature).toMatchObject({ type: 'number', min: 0, max: 10 })
    expect(byKey.cyclic).toMatchObject({ type: 'boolean', default: false })
    // Not listed in `required`, so it must not be marked as such.
    expect(byKey.ligand_ccd.required).toBe(false)
  })

  it('honours the plugin control hints a JSON Schema type cannot express', () => {
    const byKey = Object.fromEntries(
      parseParameterSchema(PROTEINHUNTER_SCHEMA).map((field) => [field.key, field]),
    )
    // A 120-residue target sequence is unreadable in a single-line input.
    expect(byKey.protein_seqs.type).toBe('textarea')
    expect(byKey.recycling_steps.advanced).toBe(true)
    expect(byKey.num_designs.advanced).toBe(false)
  })

  it('labels keys readably without requiring a title', () => {
    const byKey = Object.fromEntries(
      parseParameterSchema(PROTEINHUNTER_SCHEMA).map((field) => [field.key, field]),
    )
    expect(byKey.ligand_smiles.label).toBe('Ligand smiles')
    expect(parseParameterSchema({ properties: { mode: { type: 'string', title: 'Design mode' } } })[0].label).toBe(
      'Design mode',
    )
  })

  it('parses a schema handed over as a JSON string', () => {
    const fields = parseParameterSchema(JSON.stringify(PROTEINHUNTER_SCHEMA))
    expect(fields.find((field) => field.key === 'mode')?.type).toBe('enum')
  })

  it('returns nothing for schemas that declare no parameters', () => {
    expect(parseParameterSchema({})).toEqual([])
    expect(parseParameterSchema({ type: 'object', properties: {} })).toEqual([])
    expect(parseParameterSchema('not json')).toEqual([])
    expect(parseParameterSchema(null)).toEqual([])
  })

  it('skips properties that are not schema objects instead of rendering a broken row', () => {
    const fields = parseParameterSchema({ properties: { good: { type: 'integer' }, bad: 'nope' } })
    expect(fields.map((field) => field.key)).toEqual(['good'])
  })

  it('falls back to a text control for types it cannot render', () => {
    const fields = parseParameterSchema({
      properties: {
        missing: {},
        blank: { type: '' },
        nullable: { type: ['string', 'null'] },
        unknown: { type: 'tuple' },
        listed: { type: 'array' },
      },
    })
    expect(fields.map((field) => field.type)).toEqual(['string', 'string', 'string', 'string', 'json'])
  })
})

describe('fieldsFromParameterSchema', () => {
  it('prefers the declared schema over the built-in fallback', () => {
    const fields = fieldsFromParameterSchema(PROTEINHUNTER_SCHEMA, 'ProteinHunter (Boltz)')
    expect(fields.map((field) => field.key)).toContain('ligand_ccd')
    expect(fields.map((field) => field.key)).not.toContain('random_seed')
  })

  it('supplies every schema default so a fresh node satisfies required parameters', () => {
    const defaults = defaultsFromFields(fieldsFromParameterSchema(PROTEINHUNTER_SCHEMA, 'ProteinHunter (Boltz)'))
    expect(defaults).toMatchObject({ mode: 'binder', num_designs: 3, temperature: 1.0, cyclic: false })
    // Both ligand slots stay present and empty, which is what keeps the mutual-exclusion
    // rule satisfied until the scientist fills exactly one of them.
    expect(defaults.ligand_smiles).toBe('')
    expect(defaults.ligand_ccd).toBe('')
  })
})
