import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { TimelineEntryEditor } from './TimelineEntryEditor'
import type { TimelineEntry } from '../../lib/schemas/timeline'

const { createTimelineEntry, updateTimelineEntry, deleteTimelineEntry } = vi.hoisted(() => ({
  createTimelineEntry: vi.fn(),
  updateTimelineEntry: vi.fn(),
  deleteTimelineEntry: vi.fn(),
}))

vi.mock('../../lib/api/timeline', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api/timeline')>('../../lib/api/timeline')
  return { ...actual, createTimelineEntry, updateTimelineEntry, deleteTimelineEntry }
})

const ENTRY: TimelineEntry = {
  id: 'e1',
  project_id: 'p1',
  occurred_at: '2026-08-26T16:00:00Z',
  entry_type: 'decision',
  decision_ref: 'D8',
  lane: 'dry',
  phase: 'phase-2',
  title: 'a stop decision',
  summary: 'both arms below the gate',
  body: 'Verdict: stop.',
  outcome: 'refuted',
  provenance: { external_refs: ['lsf:3'] },
  alternatives: [{ option: 'run the next arm anyway', rejected_because: 'the gate was written first' }],
  code_refs: [],
  supersedes_id: null,
  caused_by_id: null,
  tags: ['route'],
  created_by: null,
  version: 7,
  created_at: '2026-08-26T16:00:00Z',
  updated_at: '2026-08-26T16:00:00Z',
}

beforeEach(() => {
  createTimelineEntry.mockReset().mockResolvedValue(ENTRY)
  updateTimelineEntry.mockReset().mockResolvedValue(ENTRY)
  deleteTimelineEntry.mockReset().mockResolvedValue(undefined)
})

afterEach(cleanup)

describe('recording a new entry', () => {
  it('posts the typed body to the project', async () => {
    const onClose = vi.fn()
    renderWithProviders(<TimelineEntryEditor projectId="p1" onClose={onClose} />)

    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'a gate decision' } })
    fireEvent.change(screen.getByLabelText('When (UTC)'), { target: { value: '2026-08-25T11:00' } })
    fireEvent.change(screen.getByLabelText('Decision number'), { target: { value: 'D7' } })
    fireEvent.change(screen.getByLabelText('Jobs'), { target: { value: 'j1\nj2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(createTimelineEntry).toHaveBeenCalledTimes(1))
    const [projectId, body] = createTimelineEntry.mock.calls[0]
    expect(projectId).toBe('p1')
    expect(body).toMatchObject({
      title: 'a gate decision',
      occurred_at: '2026-08-25T11:00:00Z',
      decision_ref: 'D7',
      provenance: { job_ids: ['j1', 'j2'] },
    })
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('does not send a request when a required field is missing', async () => {
    renderWithProviders(<TimelineEntryEditor projectId="p1" onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.getByText('Required.')).toBeInTheDocument())
    expect(createTimelineEntry).not.toHaveBeenCalled()
  })

  it('holds errors back until the first save attempt', () => {
    renderWithProviders(<TimelineEntryEditor projectId="p1" onClose={vi.fn()} />)
    expect(screen.queryByText('Required.')).not.toBeInTheDocument()
  })

  it('blocks a settled wet decision with no bench evidence, naming the reason', async () => {
    renderWithProviders(<TimelineEntryEditor projectId="p1" onClose={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'expressed and active' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(createTimelineEntry).toHaveBeenCalled())

    createTimelineEntry.mockClear()
    cleanup()
    renderWithProviders(
      <TimelineEntryEditor
        projectId="p1"
        entry={{ ...ENTRY, lane: 'wet', outcome: 'supported', provenance: {} }}
        onClose={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.getByText(/must name bench evidence/i)).toBeInTheDocument())
    expect(updateTimelineEntry).not.toHaveBeenCalled()
  })
})

describe('editing an existing entry', () => {
  it('loads the entry into the form', () => {
    renderWithProviders(<TimelineEntryEditor projectId="p1" entry={ENTRY} onClose={vi.fn()} />)
    expect(screen.getByLabelText('Title')).toHaveValue('a stop decision')
    expect(screen.getByLabelText('Decision number')).toHaveValue('D8')
    expect(screen.getByLabelText('External references')).toHaveValue('lsf:3')
    expect(screen.getByLabelText('Option 1')).toHaveValue('run the next arm anyway')
  })

  it('sends the loaded version so a stale tab cannot overwrite', async () => {
    renderWithProviders(<TimelineEntryEditor projectId="p1" entry={ENTRY} onClose={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'a stop decision, reviewed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(updateTimelineEntry).toHaveBeenCalledTimes(1))
    const [entryId, version, body] = updateTimelineEntry.mock.calls[0]
    expect(entryId).toBe('e1')
    expect(version).toBe(7)
    expect(body.title).toBe('a stop decision, reviewed')
  })

  it('says to reload rather than retrying when the server reports a conflict', async () => {
    updateTimelineEntry.mockRejectedValue({ response: { status: 412 } })
    renderWithProviders(<TimelineEntryEditor projectId="p1" entry={ENTRY} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/Reload and re-apply/i))
    expect(updateTimelineEntry).toHaveBeenCalledTimes(1)
  })

  it('reports other failures without claiming a conflict', async () => {
    updateTimelineEntry.mockRejectedValue({ response: { status: 500 } })
    renderWithProviders(<TimelineEntryEditor projectId="p1" entry={ENTRY} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/Could not save/i))
  })

  it('deletes with the version, after a confirmation', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderWithProviders(<TimelineEntryEditor projectId="p1" entry={ENTRY} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Delete entry' }))
    await waitFor(() => expect(deleteTimelineEntry).toHaveBeenCalledWith('e1', 7))
    confirm.mockRestore()
  })

  it('does not delete when the confirmation is declined', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderWithProviders(<TimelineEntryEditor projectId="p1" entry={ENTRY} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Delete entry' }))
    expect(deleteTimelineEntry).not.toHaveBeenCalled()
    confirm.mockRestore()
  })

  it('offers no delete control when recording a new entry', () => {
    renderWithProviders(<TimelineEntryEditor projectId="p1" onClose={vi.fn()} />)
    expect(screen.queryByRole('button', { name: 'Delete entry' })).not.toBeInTheDocument()
  })
})

describe('the alternatives editor', () => {
  it('adds and removes rows', async () => {
    renderWithProviders(<TimelineEntryEditor projectId="p1" entry={ENTRY} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Add a closed branch' }))
    expect(screen.getByLabelText('Option 2')).toBeInTheDocument()

    fireEvent.click(screen.getAllByRole('button', { name: 'Remove' })[1])
    await waitFor(() => expect(screen.queryByLabelText('Option 2')).not.toBeInTheDocument())
  })

  it('refuses to save an option whose reason is blank', async () => {
    renderWithProviders(<TimelineEntryEditor projectId="p1" entry={ENTRY} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Add a closed branch' }))
    fireEvent.change(screen.getByLabelText('Option 2'), { target: { value: 'read it by the other unit' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(screen.getByText(/An option and its reason go together/i)).toBeInTheDocument(),
    )
    expect(updateTimelineEntry).not.toHaveBeenCalled()
  })
})
