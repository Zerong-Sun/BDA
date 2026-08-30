import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { InputBindingPanel } from './InputBindingPanel'
import type { ModelPlugin } from '../../lib/schemas/registry'
import type { Artifact } from '../../lib/schemas/artifact'
import type { WorkflowNode } from '../../lib/schemas/workflow'

const plugin = (overrides: Partial<ModelPlugin> = {}): ModelPlugin =>
  ({
    id: 'plugin-mpnn',
    plugin_key: 'ProteinMPNN',
    plugin_version: '1.0.0',
    name: 'ProteinMPNN',
    container_image: 'mpnn:1.0.0',
    command: 'run.sh',
    parameter_schema: {},
    output_schema: {},
    enabled: true,
    validation_status: 'valid',
    validated_at: null,
    validation_errors: [],
    version: 1,
    created_at: '',
    updated_at: '',
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
    resources: {},
    runtime_mode: 'container',
    output_parser: null,
    ...overrides,
  }) as ModelPlugin

const node = (key: string, pluginId: string): WorkflowNode =>
  ({
    id: `node-${key}`,
    workflow_run_id: 'wf',
    node_key: key,
    node_type: 'model',
    model_plugin: 'ProteinMPNN',
    model_plugin_id: pluginId,
    container_image: null,
    command: null,
    queue: null,
    status: 'draft',
    parameters: {},
    input_bindings: [],
    error_message: null,
    version: 1,
    created_at: '',
    updated_at: '',
  }) as WorkflowNode

const artifact = (id: string, type: string, filename: string): Artifact =>
  ({
    id,
    project_id: 'p',
    artifact_type: type,
    filename,
    // Browsers mis-sniff .pdb as this; the panel must still offer the file.
    content_type: 'application/vnd.palm',
    size_bytes: 10,
    checksum_sha256: 'a'.repeat(64),
    status: 'available',
    lineage: {},
    created_at: '',
    updated_at: '',
  }) as unknown as Artifact

describe('InputBindingPanel', () => {
  it('offers project files whose artifact_type the port accepts', async () => {
    const onChange = vi.fn()
    render(
      <InputBindingPanel
        node={node('mpnn', 'plugin-mpnn')}
        plugin={plugin()}
        nodes={[]}
        pluginsByNodeKey={{}}
        artifacts={[
          artifact('a1', 'backbone_set', 'design_0.pdb'),
          artifact('a2', 'score_table', 'scores.csv'),
        ]}
        bindings={[]}
        onChange={onChange}
      />,
    )

    fireEvent.click(screen.getByRole('combobox', { name: 'backbone' }))
    const artifactSource = await screen.findByRole('option', { name: 'Project file' })
    fireEvent.pointerDown(artifactSource, { button: 0 })
    fireEvent.pointerUp(artifactSource, { button: 0 })
    fireEvent.click(artifactSource)
    expect(onChange).toHaveBeenCalledWith([
      { port: 'backbone', source: 'artifact', artifact_id: '' },
    ])
  })

  it('does not filter on content type, which browsers get wrong for scientific files', async () => {
    render(
      <InputBindingPanel
        node={node('mpnn', 'plugin-mpnn')}
        plugin={plugin()}
        nodes={[]}
        pluginsByNodeKey={{}}
        artifacts={[artifact('a1', 'backbone_set', 'design_0.pdb')]}
        bindings={[{ port: 'backbone', source: 'artifact', artifact_id: '' }]}
        onChange={vi.fn()}
      />,
    )
    // The .pdb arrives as application/vnd.palm yet must still be selectable.
    fireEvent.click(screen.getByRole('combobox', { name: 'backbone artifact' }))
    expect(await screen.findByRole('option', { name: /design_0\.pdb/ })).toBeTruthy()
  })

  it('excludes files whose artifact_type the port rejects', async () => {
    render(
      <InputBindingPanel
        node={node('mpnn', 'plugin-mpnn')}
        plugin={plugin()}
        nodes={[]}
        pluginsByNodeKey={{}}
        artifacts={[artifact('a2', 'score_table', 'scores.csv')]}
        bindings={[{ port: 'backbone', source: 'artifact', artifact_id: '' }]}
        onChange={vi.fn()}
      />,
    )
    expect(screen.queryByRole('combobox', { name: 'backbone artifact' })).toBeNull()
  })

  it('offers only upstream outputs whose kind matches the port', async () => {
    const producer = plugin({
      id: 'plugin-rfd',
      name: 'RFdiffusion',
      input_ports: [],
      output_ports: [
        { name: 'backbones', kind: 'protein_structure', artifact_type: 'backbone_set', filename_glob: '*', description: '' },
        { name: 'log', kind: 'tabular', artifact_type: 'score_table', filename_glob: '*', description: '' },
      ],
    })
    render(
      <InputBindingPanel
        node={node('mpnn', 'plugin-mpnn')}
        plugin={plugin()}
        nodes={[node('rfd', 'plugin-rfd'), node('mpnn', 'plugin-mpnn')]}
        pluginsByNodeKey={{ rfd: producer, mpnn: plugin() }}
        artifacts={[]}
        bindings={[{ port: 'backbone', source: 'upstream', from_node: '', from_port: '' }]}
        onChange={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('combobox', { name: 'backbone upstream' }))
    expect(await screen.findByRole('option', { name: 'rfd · backbones' })).toBeTruthy()
    // Wrong kind: a score table cannot feed a structure port.
    expect(screen.queryByRole('option', { name: 'rfd · log' })).toBeNull()
  })

  it('offers ProteinMPNN sequences on superfold sequence input and clears its structure alternative', async () => {
    const onChange = vi.fn()
    const mpnn = plugin({
      output_ports: [
        { name: 'sequences', kind: 'protein_sequence', artifact_type: 'sequence_set', filename_glob: '*.fa*', description: '' },
      ],
    })
    const superfold = plugin({
      id: 'plugin-superfold',
      plugin_key: 'superfold',
      name: 'superfold',
      input_ports: [
        {
          name: 'structures', kind: 'protein_structure', accepts: ['predicted_structure'],
          content_types: [], required: true, multiple: true, description: '',
          exclusive_group: 'superfold_input_source',
        },
        {
          name: 'sequences', kind: 'protein_sequence', accepts: ['sequence_set'],
          content_types: [], required: true, multiple: true, description: '',
          exclusive_group: 'superfold_input_source',
        },
      ],
    })
    const foldNode = node('fold', 'plugin-superfold')
    render(
      <InputBindingPanel
        node={foldNode}
        plugin={superfold}
        nodes={[node('mpnn', 'plugin-mpnn'), foldNode]}
        pluginsByNodeKey={{ mpnn, fold: superfold }}
        artifacts={[]}
        bindings={[
          { port: 'structures', source: 'artifact', artifact_id: 'old-structure' },
          { port: 'sequences', source: 'upstream', from_node: '', from_port: '' },
        ]}
        onChange={onChange}
      />,
    )

    fireEvent.click(screen.getByRole('combobox', { name: 'sequences upstream' }))
    const mpnnSequences = await screen.findByRole('option', { name: 'mpnn · sequences' })
    fireEvent.pointerDown(mpnnSequences, { button: 0 })
    fireEvent.pointerUp(mpnnSequences, { button: 0 })
    fireEvent.click(mpnnSequences)

    expect(onChange).toHaveBeenCalledWith([
      { port: 'sequences', source: 'upstream', from_node: 'mpnn', from_port: 'sequences' },
    ])
  })

  it('flags a required port that has no binding', () => {
    const { container } = render(
      <InputBindingPanel
        node={node('mpnn', 'plugin-mpnn')}
        plugin={plugin()}
        nodes={[]}
        pluginsByNodeKey={{}}
        artifacts={[]}
        bindings={[]}
        onChange={vi.fn()}
      />,
    )
    const row = container.querySelector('[data-testid="input-port-backbone"]')
    expect(row?.className).toContain('border-status-danger/50')
  })

  it('explains itself when the node has no registry plugin', () => {
    render(
      <InputBindingPanel
        node={node('mpnn', 'plugin-mpnn')}
        plugin={undefined}
        nodes={[]}
        pluginsByNodeKey={{}}
        artifacts={[]}
        bindings={[]}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText(/registry plugin|注册表插件/)).toBeTruthy()
  })
})
