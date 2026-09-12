import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/handlers'
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
    decided_by: 'human',
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

/** The picker shows real rows, so a test that wants to cite one has to have one. */
function projectHasJob(id: string, externalId: string) {
  server.use(
    http.get('/api/v2/jobs', () =>
      HttpResponse.json({ items: [{ id, external_id: externalId, status: 'succeeded' }], next_cursor: null }),
    ),
  )
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
    projectHasJob('11111111-1111-1111-1111-111111111111', 'lsf-8812')
    renderWithProviders(<TimelineEntryEditor projectId="p1" onClose={onClose} />)

    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'a gate decision' } })
    fireEvent.change(screen.getByLabelText('When (UTC)'), { target: { value: '2026-08-25T11:00' } })
    fireEvent.change(screen.getByLabelText('Decision number'), { target: { value: 'D7' } })
    // Cited by choosing the row, not by typing an id: there is no box to type one into,
    // which is the whole mechanism. A free-text field gets answered with whatever the
    // writer has to hand, and that is how 49 LSF job numbers became unresolvable strings.
    fireEvent.click(await screen.findByText(/lsf-8812/))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(createTimelineEntry).toHaveBeenCalledTimes(1))
    const [projectId, body] = createTimelineEntry.mock.calls[0]
    expect(projectId).toBe('p1')
    expect(body).toMatchObject({
      title: 'a gate decision',
      occurred_at: '2026-08-25T11:00:00Z',
      decision_ref: 'D7',
      provenance: { job_ids: ['11111111-1111-1111-1111-111111111111'] },
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

describe('choosing what an entry replaces', () => {
  const OTHER: TimelineEntry = { ...ENTRY, id: 'e2', decision_ref: 'D6', title: 'an earlier call' }

  it('offers the project’s other entries, and not itself', () => {
    renderWithProviders(
      <TimelineEntryEditor projectId="p1" entry={ENTRY} entries={[ENTRY, OTHER]} onClose={vi.fn()} />,
    )
    // Radix renders options on open; the trigger is what must exist unconditionally.
    expect(screen.getByLabelText('Replaces')).toBeInTheDocument()
    expect(screen.getByLabelText('Answers')).toBeInTheDocument()
  })

  it('sends the chosen edge on save', async () => {
    renderWithProviders(
      <TimelineEntryEditor
        projectId="p1"
        entry={{ ...ENTRY, supersedes_id: 'e2' }}
        entries={[ENTRY, OTHER]}
        onClose={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(updateTimelineEntry).toHaveBeenCalled())
    expect(updateTimelineEntry.mock.calls[0][2].supersedes_id).toBe('e2')
  })

  it('blocks an entry that supersedes itself before the request goes out', async () => {
    renderWithProviders(
      <TimelineEntryEditor
        projectId="p1"
        entry={{ ...ENTRY, supersedes_id: ENTRY.id }}
        entries={[ENTRY, OTHER]}
        onClose={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.getByText(/cannot point at itself/i)).toBeInTheDocument())
    expect(updateTimelineEntry).not.toHaveBeenCalled()
  })
})

describe('citing evidence', () => {
  it('has no box to type an owned id into', async () => {
    // The keys that name platform rows are chosen, not typed. `artifact_ids` stayed empty
    // for the life of the table while `external_refs` filled with strings; the field was
    // never the problem, the text box was.
    projectHasJob('11111111-1111-1111-1111-111111111111', 'lsf-8812')
    renderWithProviders(<TimelineEntryEditor projectId="p1" onClose={vi.fn()} />)

    await screen.findByText(/lsf-8812/)
    expect(screen.queryByRole('textbox', { name: 'Jobs' })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Artifacts' })).not.toBeInTheDocument()
  })

  it('keeps a free-text box for the one key that names things we do not own', () => {
    // An LSF job id is the case `external_refs` exists for, so demanding an id here would
    // be wrong - and it is the exception that lets the rule be strict everywhere else.
    renderWithProviders(<TimelineEntryEditor projectId="p1" onClose={vi.fn()} />)
    expect(screen.getByRole('textbox', { name: 'External references' })).toBeInTheDocument()
  })

  it('warns when a typed id addresses nothing', () => {
    renderWithProviders(<TimelineEntryEditor projectId="p1" onClose={vi.fn()} />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Autopilot campaigns' }), {
      target: { value: '4180231' },
    })
    expect(screen.getByText(/nothing can resolve it/i)).toBeInTheDocument()
  })

  it('still shows a cited row that is no longer in the list', async () => {
    // Dropping it on the next save would rewrite the record silently.
    projectHasJob('11111111-1111-1111-1111-111111111111', 'lsf-8812')
    renderWithProviders(
      <TimelineEntryEditor
        projectId="p1"
        entry={{ ...ENTRY, provenance: { job_ids: ['99999999-9999-9999-9999-999999999999'] } }}
        onClose={vi.fn()}
      />,
    )
    expect(await screen.findByText(/also citing: 99999999/i)).toBeInTheDocument()
  })
})
