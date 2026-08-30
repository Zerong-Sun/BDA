import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ParameterSchemaForm } from './ParameterSchemaForm'
import { defaultsFromFields, fieldsFromParameterSchema } from '../../lib/forms/parameterSchema'

// The shape a plugin onboarded as pure data actually registers: JSON Schema, the format
// PLUGIN_INTERFACE.md defines and preflight validates against.
const PROTEINHUNTER_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  properties: {
    mode: { type: 'string', enum: ['binder', 'unconditional'], default: 'binder' },
    protein_seqs: { type: 'string', default: '', 'x-bda-field-type': 'textarea' },
    ligand_ccd: { type: 'string', default: '', description: 'PDB chemical component code.' },
    num_designs: { type: 'integer', minimum: 1, maximum: 10000, default: 3 },
    high_iptm_threshold: { type: 'number', minimum: 0, maximum: 1, default: 0.8 },
    recycling_steps: { type: 'integer', default: 3, 'x-bda-advanced': true },
  },
  required: ['mode', 'num_designs'],
}

function renderForm(values: Record<string, unknown> = {}) {
  const onChange = vi.fn()
  const fields = fieldsFromParameterSchema(PROTEINHUNTER_SCHEMA, 'ProteinHunter (Boltz)')
  render(
    <ParameterSchemaForm
      schema={{ fields }}
      values={{ ...defaultsFromFields(fields), ...values }}
      onChange={onChange}
    />,
  )
  return onChange
}

describe('ParameterSchemaForm with a JSON Schema plugin', () => {
  it('renders an editable control for every declared parameter', () => {
    renderForm()
    expect(screen.getByLabelText('Ligand ccd')).toBeTruthy()
    expect(screen.getByLabelText(/^Num designs/)).toBeTruthy()
    expect(screen.getByLabelText('High iptm threshold')).toBeTruthy()
    // Before this, a JSON Schema plugin fell back to a single `random_seed` field and its
    // required parameters could not be set from the UI at all.
    expect(screen.queryByLabelText('Random seed')).toBeNull()
  })

  it('reports the ligand target the scientist types', () => {
    const onChange = renderForm()
    fireEvent.change(screen.getByLabelText('Ligand ccd'), { target: { value: 'TCI' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ ligand_ccd: 'TCI' }))
  })

  it('keeps the other schema defaults when one parameter changes', () => {
    const onChange = renderForm()
    fireEvent.change(screen.getByLabelText(/^Num designs/), { target: { value: '1000' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ num_designs: 1000, mode: 'binder', high_iptm_threshold: 0.8 }),
    )
  })

  it('gives a long target sequence a multi-line control', () => {
    renderForm()
    expect(screen.getByLabelText('Protein seqs').tagName).toBe('TEXTAREA')
    expect(screen.getByLabelText('Ligand ccd').tagName).toBe('INPUT')
  })

  it('carries the numeric bounds the schema declares onto the input', () => {
    renderForm()
    const designs = screen.getByLabelText(/^Num designs/)
    expect(designs.getAttribute('min')).toBe('1')
    expect(designs.getAttribute('max')).toBe('10000')
    expect(designs.getAttribute('type')).toBe('number')
  })

  it('marks the parameters the schema requires', () => {
    renderForm()
    expect(screen.getAllByTitle('Required by the plugin schema')).toHaveLength(2)
  })

  it('folds annotated parameters behind the advanced disclosure', () => {
    renderForm()
    const trigger = screen.getByRole('button', { name: 'Advanced parameters' })
    expect(trigger).toBeTruthy()
    // Collapsed to start with, so the primary list stays short.
    expect(screen.queryByLabelText('Recycling steps')).toBeNull()
    fireEvent.click(trigger)
    expect(screen.getByLabelText('Recycling steps')).toBeTruthy()
  })
})
