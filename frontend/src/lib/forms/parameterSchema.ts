export interface ParameterFieldDefinition {
  key: string
  label?: string
  type?:
    | 'integer'
    | 'number'
    | 'boolean'
    | 'enum'
    | 'string'
    | 'textarea'
    | 'json'
    | 'artifact_ref'
    | 'residue_selector'
  default?: unknown
  min?: number
  max?: number
  options?: Array<string | { label: string; value: string }>
  help?: string
  advanced?: boolean
  required?: boolean
}

export interface ParameterSchemaMetadata {
  workflowNote?: string
  exclusiveWith?: string[]
  recommendedAfter?: string[]
  recommendedBefore?: string[]
}

function safeJson(value: string): unknown {
  try {
    return JSON.parse(value)
  } catch {
    return undefined
  }
}

// PLUGIN_INTERFACE.md declares parameter_schema as JSON Schema, and preflight validates
// node parameters against it with Draft 2020-12. A plugin onboarded as pure data therefore
// has no `fields` block, and rendering only that private shape left such plugins with no
// editable parameters at all — every required one then failed preflight with no way to fix
// it from the UI.
const JSON_SCHEMA_TYPES: Record<string, ParameterFieldDefinition['type']> = {
  integer: 'integer',
  number: 'number',
  boolean: 'boolean',
  string: 'string',
  object: 'json',
  array: 'json',
}

// Field types a plugin may request explicitly, for shapes JSON Schema cannot express:
// a long sequence or SMILES needs a textarea, an artifact reference needs the picker.
const FIELD_TYPE_OVERRIDES: ReadonlySet<string> = new Set([
  'string',
  'textarea',
  'json',
  'artifact_ref',
  'residue_selector',
])

function humanizeKey(key: string): string {
  return key
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/^\w/, (character) => character.toUpperCase())
}

function firstConcreteType(value: unknown): string | undefined {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    return value.find((item): item is string => typeof item === 'string' && item !== 'null')
  }
  return undefined
}

function numberOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function fieldFromJsonSchemaProperty(
  key: string,
  property: Record<string, unknown>,
  required: boolean,
): ParameterFieldDefinition {
  const enumValues = Array.isArray(property.enum)
    ? property.enum.filter((item): item is string => typeof item === 'string')
    : []
  const declaredType = firstConcreteType(property.type)
  const mappedType = declaredType ? JSON_SCHEMA_TYPES[declaredType] : undefined
  const override = property['x-bda-field-type']
  const type: ParameterFieldDefinition['type'] =
    typeof override === 'string' && FIELD_TYPE_OVERRIDES.has(override)
      ? (override as ParameterFieldDefinition['type'])
      : enumValues.length > 0
        ? 'enum'
        : (mappedType ?? 'string')

  return {
    key,
    label: typeof property.title === 'string' ? property.title : humanizeKey(key),
    type,
    default: property.default,
    min: numberOrUndefined(property.minimum),
    max: numberOrUndefined(property.maximum),
    options: enumValues.length > 0 ? enumValues : undefined,
    help: typeof property.description === 'string' ? property.description : undefined,
    advanced: property['x-bda-advanced'] === true,
    required,
  }
}

function fieldsFromJsonSchema(schema: Record<string, unknown>): ParameterFieldDefinition[] {
  const properties = schema.properties
  if (!properties || typeof properties !== 'object') return []
  const required = new Set(
    Array.isArray(schema.required)
      ? schema.required.filter((item): item is string => typeof item === 'string')
      : [],
  )
  return Object.entries(properties as Record<string, unknown>)
    .filter((entry): entry is [string, Record<string, unknown>] =>
      Boolean(entry[1] && typeof entry[1] === 'object' && !Array.isArray(entry[1])),
    )
    .map(([key, property]) => fieldFromJsonSchemaProperty(key, property, required.has(key)))
}

export function parseParameterSchema(schema: unknown): ParameterFieldDefinition[] {
  const parsed = typeof schema === 'string' ? safeJson(schema) : schema
  if (!parsed || typeof parsed !== 'object') return []
  const fields = (parsed as { fields?: unknown }).fields
  if (!Array.isArray(fields)) return fieldsFromJsonSchema(parsed as Record<string, unknown>)
  return fields
    .filter((field): field is ParameterFieldDefinition => {
      return Boolean(field && typeof field === 'object' && typeof (field as { key?: unknown }).key === 'string')
    })
    .map((field) => ({
      type: 'string',
      ...field,
    }))
}

export function parseParameterSchemaMetadata(schema: unknown): ParameterSchemaMetadata {
  const parsed = typeof schema === 'string' ? safeJson(schema) : schema
  if (!parsed || typeof parsed !== 'object') return {}
  const record = parsed as {
    workflow_note?: unknown
    exclusive_with?: unknown
    recommended_after?: unknown
    recommended_before?: unknown
  }
  return {
    workflowNote: typeof record.workflow_note === 'string' ? record.workflow_note : undefined,
    exclusiveWith: Array.isArray(record.exclusive_with) ? record.exclusive_with.filter((item): item is string => typeof item === 'string') : undefined,
    recommendedAfter: Array.isArray(record.recommended_after) ? record.recommended_after.filter((item): item is string => typeof item === 'string') : undefined,
    recommendedBefore: Array.isArray(record.recommended_before) ? record.recommended_before.filter((item): item is string => typeof item === 'string') : undefined,
  }
}

function fallbackFields(modelName?: string): ParameterFieldDefinition[] {
  if (modelName === 'RFdiffusion') {
    return [
      { key: 'inference.input_pdb', label: 'Input PDB', type: 'artifact_ref', default: '', help: 'Target or motif PDB passed as inference.input_pdb.' },
      { key: 'contigmap.contigs', label: 'Contigs', type: 'string', default: '[A1-150/0 70-100]', help: 'Hydra contig list, e.g. target residues plus chain break and binder length range.' },
      { key: 'ppi.hotspot_res', label: 'Hotspot residues', type: 'string', default: '[A59,A83,A91]' },
      { key: 'inference.num_designs', label: 'Number of designs', type: 'integer', default: 100, min: 1, max: 100000 },
      { key: 'inference.output_prefix', label: 'Output prefix', type: 'string', default: 'outputs/rfdiffusion/design', advanced: true },
      { key: 'diffuser.partial_T', label: 'Partial diffusion steps', type: 'integer', default: 0, min: 0, max: 50, advanced: true },
      { key: 'diffuser.T', label: 'Diffusion steps', type: 'integer', default: 50, min: 1, max: 200, advanced: true },
      { key: 'denoiser.noise_scale_ca', label: 'CA noise scale', type: 'number', default: 1.0, min: 0, max: 5, advanced: true },
      { key: 'denoiser.noise_scale_frame', label: 'Frame noise scale', type: 'number', default: 1.0, min: 0, max: 5, advanced: true },
      { key: 'contigmap.inpaint_seq', label: 'Inpaint sequence', type: 'string', default: '', advanced: true },
      { key: 'contigmap.inpaint_str', label: 'Inpaint structure', type: 'string', default: '', advanced: true },
      { key: 'contigmap.provide_seq', label: 'Provide sequence', type: 'string', default: '', advanced: true },
      { key: 'inference.ckpt_override_path', label: 'Checkpoint override', type: 'enum', default: '', options: ['', 'models/ActiveSite_ckpt.pt', 'models/Complex_beta_ckpt.pt'], advanced: true },
      { key: 'inference.symmetry', label: 'Symmetry', type: 'string', default: '', advanced: true },
      { key: 'potentials.guiding_potentials', label: 'Guiding potentials', type: 'json', default: '[]', advanced: true },
      { key: 'potentials.guide_scale', label: 'Potential guide scale', type: 'number', default: 1.0, min: 0, max: 20, advanced: true },
    ]
  }
  if (modelName === 'ProteinMPNN') {
    return [
      { key: 'pdb_path', label: 'Single PDB path', type: 'artifact_ref', default: '' },
      { key: 'jsonl_path', label: 'Parsed PDB JSONL', type: 'artifact_ref', default: '' },
      { key: 'out_folder', label: 'Output folder', type: 'string', default: 'outputs/proteinmpnn' },
      { key: 'num_seq_per_target', label: 'Sequences per target', type: 'integer', default: 8, min: 1, max: 10000 },
      { key: 'batch_size', label: 'Batch size', type: 'integer', default: 1, min: 1, max: 1024 },
      { key: 'sampling_temp', label: 'Sampling temperatures', type: 'string', default: '0.1', help: 'Space-separated temperatures such as 0.1 0.15 0.2.' },
      { key: 'model_name', label: 'Model name', type: 'enum', default: 'v_48_020', options: ['v_48_002', 'v_48_010', 'v_48_020', 'v_48_030'] },
      { key: 'pdb_path_chains', label: 'Designed chains', type: 'string', default: '' },
      { key: 'fixed_positions_jsonl', label: 'Fixed positions JSONL', type: 'artifact_ref', default: '', advanced: true },
      { key: 'omit_AAs', label: 'Omit amino acids', type: 'string', default: 'X', advanced: true },
      { key: 'bias_AA_jsonl', label: 'AA bias JSONL', type: 'artifact_ref', default: '', advanced: true },
      { key: 'pssm_jsonl', label: 'PSSM JSONL', type: 'artifact_ref', default: '', advanced: true },
      { key: 'pssm_multi', label: 'PSSM blend', type: 'number', default: 0, min: 0, max: 1, advanced: true },
      { key: 'tied_positions_jsonl', label: 'Tied positions JSONL', type: 'artifact_ref', default: '', advanced: true },
      { key: 'backbone_noise', label: 'Backbone noise', type: 'number', default: 0, min: 0, max: 1, advanced: true },
      { key: 'use_soluble_model', label: 'Use soluble model', type: 'boolean', default: false, advanced: true },
      { key: 'ca_only', label: 'CA-only model', type: 'boolean', default: false, advanced: true },
    ]
  }
  if (modelName === 'AlphaFold2') {
    return [
      { key: 'fasta_paths', label: 'FASTA paths', type: 'artifact_ref', default: '' },
      { key: 'output_dir', label: 'Output directory', type: 'string', default: 'outputs/alphafold' },
      { key: 'data_dir', label: 'Data directory', type: 'string', default: '/data/alphafold' },
      { key: 'model_preset', label: 'Model preset', type: 'enum', default: 'multimer', options: ['monomer', 'monomer_casp14', 'monomer_ptm', 'multimer'] },
      { key: 'db_preset', label: 'Database preset', type: 'enum', default: 'reduced_dbs', options: ['full_dbs', 'reduced_dbs'] },
      { key: 'max_template_date', label: 'Max template date', type: 'string', default: '2026-01-01' },
      { key: 'num_multimer_predictions_per_model', label: 'Multimer predictions/model', type: 'integer', default: 5, min: 1, max: 20 },
      { key: 'models_to_relax', label: 'Models to relax', type: 'enum', default: 'best', options: ['all', 'best', 'none'] },
      { key: 'use_gpu_relax', label: 'GPU relax', type: 'boolean', default: true },
      { key: 'use_precomputed_msas', label: 'Use precomputed MSAs', type: 'boolean', default: false, advanced: true },
      { key: 'benchmark', label: 'Benchmark mode', type: 'boolean', default: false, advanced: true },
      { key: 'jackhmmer_n_cpu', label: 'JackHMMER CPUs', type: 'integer', default: 8, min: 1, max: 256, advanced: true },
    ]
  }
  if (modelName === 'Rosetta') {
    return [
      { key: 'application', label: 'Application', type: 'enum', default: 'rosetta_scripts', options: ['rosetta_scripts', 'relax', 'InterfaceAnalyzer', 'cartesian_ddg'] },
      { key: 's', label: 'Input structure', type: 'artifact_ref', default: '' },
      { key: 'parser:protocol', label: 'RosettaScripts XML', type: 'artifact_ref', default: '' },
      { key: 'nstruct', label: 'N structures', type: 'integer', default: 1, min: 1, max: 10000 },
      { key: 'score:weights', label: 'Score weights', type: 'enum', default: 'ref2015', options: ['ref2015', 'beta_nov16', 'beta_cart', 'talaris2014'] },
      { key: 'interface', label: 'Interface chains', type: 'string', default: 'A_B' },
      { key: 'ex1', label: 'Extra chi 1 rotamers', type: 'boolean', default: true },
      { key: 'ex2', label: 'Extra chi 2 rotamers', type: 'boolean', default: true },
      { key: 'relax:constrain_relax_to_start_coords', label: 'Constrain to start coords', type: 'boolean', default: true, advanced: true },
      { key: 'relax:ramp_constraints', label: 'Ramp constraints', type: 'boolean', default: false, advanced: true },
      { key: 'parser:script_vars', label: 'Script variables', type: 'string', default: '', advanced: true },
      { key: 'resfile', label: 'Resfile', type: 'artifact_ref', default: '', advanced: true },
      { key: 'constraints:cst_fa_file', label: 'Constraint file', type: 'artifact_ref', default: '', advanced: true },
    ]
  }
  return [
    { key: 'random_seed', label: 'Random seed', type: 'integer', default: 42, advanced: true },
  ]
}

export function fieldsFromParameterSchema(schema: unknown, modelName?: string): ParameterFieldDefinition[] {
  const fields = parseParameterSchema(schema)
  return fields.length > 0 ? fields : fallbackFields(modelName)
}

export function defaultsFromFields(fields: ParameterFieldDefinition[]): Record<string, unknown> {
  return fields.reduce<Record<string, unknown>>((acc, field) => {
    if (field.default !== undefined) acc[field.key] = field.default
    return acc
  }, {})
}
