/**
 * Regression cover for the read-only contract the manual UI review flagged.
 *
 * The server refuses edits once a run leaves 'draft', so offering them here produced a
 * 409 only after the user had already done the work. These assert the controls are
 * actually disabled rather than merely styled as such.
 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { InputBindingPanel } from './InputBindingPanel'
import { ParameterSchemaForm } from '../plugins'
import type { ModelPlugin } from '../../lib/schemas/registry'
import type { WorkflowNode } from '../../lib/schemas/workflow'

vi.mock('../../lib/i18n', () => ({
  useI18n: () => ({
    t: {
      workflowExt: {
        inspector: {
          inputSourceNone: 'Not bound',
          inputSourceArtifact: 'Project file',
          inputSourceUpstream: 'Upstream node',
          inputChooseArtifact: 'Choose a file',
          inputChooseUpstream: 'Choose an upstream output',
          inputNoCandidates: 'No candidates',
          inputNoUpstream: 'No upstream outputs',
          inputRequired: 'Required',
          inputAlternative: 'Alternative',
          inputUnsatisfied: 'Unsatisfied',
        },
      },
      plugins: { parameterSchema: { noSchema: 'No schema', advancedParameters: 'Advanced', changed: 'changed' } },
    },
    format: (template: string) => template,
  }),
}))

const plugin = {
  id: 'plugin-mpnn',
  name: 'ProteinMPNN',
  input_ports: [
    {
      name: 'backbone',
      kind: 'protein_structure',
      accepts: ['backbone_set'],
      content_types: [],
      required: true,
      multiple: false,
      description: '',
    },
  ],
  output_ports: [],
} as unknown as ModelPlugin

const node = {
  id: 'node-mpnn',
  workflow_run_id: 'wf',
  node_key: 'mpnn',
  node_type: 'model',
  model_plugin: 'ProteinMPNN',
  model_plugin_id: 'plugin-mpnn',
  status: 'succeeded',
  parameters: {},
  input_bindings: [],
} as unknown as WorkflowNode

describe('read-only workflow editing', () => {
  it('does not let a finished run be rebound', () => {
    render(
      <InputBindingPanel
        node={node}
        plugin={plugin}
        nodes={[]}
        pluginsByNodeKey={{}}
        artifacts={[]}
        bindings={[]}
        onChange={vi.fn()}
        readOnly
      />,
    )

    expect(screen.getByLabelText('backbone')).toBeDisabled()
  })

  it('still allows rebinding while the run is editable', () => {
    render(
      <InputBindingPanel
        node={node}
        plugin={plugin}
        nodes={[]}
        pluginsByNodeKey={{}}
        artifacts={[]}
        bindings={[]}
        onChange={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('backbone')).not.toBeDisabled()
  })

  const parameterSchema = {
    fields: [{ key: 'num_designs', label: 'num_designs', type: 'integer', default: 10 }],
  }

  it('does not let a finished run have its parameters retyped', () => {
    render(
      <ParameterSchemaForm
        schema={parameterSchema}
        values={{ num_designs: 10 }}
        onChange={vi.fn()}
        disabled
      />,
    )

    expect(screen.getByLabelText('num_designs')).toBeDisabled()
  })

  it('still allows parameter edits while the run is editable', () => {
    render(
      <ParameterSchemaForm
        schema={parameterSchema}
        values={{ num_designs: 10 }}
        onChange={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('num_designs')).not.toBeDisabled()
  })
})
