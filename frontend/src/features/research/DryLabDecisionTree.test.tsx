import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { DryLabDecisionTree } from './DryLabDecisionTree'

const listAllTimeline = vi.hoisted(() => vi.fn())

vi.mock('../../lib/api/timeline', () => ({ listAllTimeline }))

const entry = (overrides: Record<string, unknown> = {}) => ({
  id: 'decision-one',
  project_id: 'project-one',
  occurred_at: '2026-08-01T10:00:00Z',
  entry_type: 'decision',
  phase: 'binder-route-a',
  title: 'Advance the restrained backbone route',
  summary: 'The restrained route retained the target interface.',
  body: '## Decision basis\n\nAdvance because the interface checks passed.',
  outcome: 'supported',
  provenance: { workflow_run_ids: ['workflow-one'], candidate_ids: ['candidate-one'] },
  code_refs: [{ path: 'qm-scripts/plugins/rfdiffusion/run.sh', role: 'backbone generation' }],
  supersedes_id: null,
  caused_by_id: null,
  tags: ['dry-lab'],
  created_by: 'user-one',
  version: 1,
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
  ...overrides,
})

describe('DryLabDecisionTree', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
    listAllTimeline.mockReset()
  })

  afterEach(cleanup)

  it('groups computational decisions into route branches and exposes the decision document', async () => {
    listAllTimeline.mockResolvedValue([
      entry({
        id: 'problem-one',
        entry_type: 'problem',
        title: 'Interface drift blocked the route',
        body: '',
        occurred_at: '2026-07-31T10:00:00Z',
        outcome: 'refuted',
      }),
      entry(),
      entry({
        id: 'result-one',
        entry_type: 'result',
        title: 'Interface checks completed',
        body: '',
        occurred_at: '2026-08-02T10:00:00Z',
        caused_by_id: 'problem-one',
      }),
      entry({
        id: 'decision-two',
        phase: 'binder-route-b',
        title: 'Hold the exploratory route',
        outcome: 'inconclusive',
        occurred_at: '2026-08-03T10:00:00Z',
        supersedes_id: 'decision-one',
      }),
    ])

    renderWithProviders(<DryLabDecisionTree projectId="project-one" />)

    expect(await screen.findByText('binder-route-a')).toBeInTheDocument()
    expect(screen.getByText('binder-route-b')).toBeInTheDocument()
    expect(screen.getByText('Advance the restrained backbone route', { selector: 'h4' })).toBeInTheDocument()
    const documents = screen.getAllByRole('button', { name: 'View decision document' })
    expect(documents).not.toHaveLength(0)
    fireEvent.click(documents[0])
    expect(await screen.findByText('Decision basis')).toBeInTheDocument()
    expect(screen.getAllByText('workflow_run_ids: workflow-one')).not.toHaveLength(0)
    expect(screen.getAllByText('qm-scripts/plugins/rfdiffusion/run.sh · backbone generation')).not.toHaveLength(0)
    expect(screen.getByText('Answers an earlier problem:')).toBeInTheDocument()
    expect(screen.getByText('Interface drift blocked the route', { selector: 'dd' })).toBeInTheDocument()
    expect(screen.getByText('Supersedes an earlier entry:')).toBeInTheDocument()
    expect(screen.getByText('Advance the restrained backbone route', { selector: 'dd' })).toBeInTheDocument()
    expect(listAllTimeline).toHaveBeenCalledWith('project-one')
  })

  it('shows an honest empty state without inventing a decision tree', async () => {
    listAllTimeline.mockResolvedValue([])
    renderWithProviders(<DryLabDecisionTree projectId="project-one" />)
    expect(await screen.findByText(/No structured computational decisions/)).toBeInTheDocument()
  })

  it('offers a retry and recovers after a timeline request fails', async () => {
    listAllTimeline
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce([entry()])

    renderWithProviders(<DryLabDecisionTree projectId="project-one" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the project timeline.')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Advance the restrained backbone route')).toBeInTheDocument()
    expect(listAllTimeline).toHaveBeenCalledTimes(2)
  })
})
