import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { CopilotChain } from './CopilotChain'

/**
 * The chain record, which had no UI at all.
 *
 * The assertions worth keeping are about the unsupported claim. A claim citing
 * nothing is not an error and is not hidden: the operator made it, the server
 * recorded it as unsupported rather than dropping it, and a reader looking for
 * what to check should find it first. A view that rendered it like any other
 * claim would undo the one property that makes this table worth having.
 */

afterEach(cleanup)

const HANDOFF = {
  id: 'h1',
  from_bot: 'librarian',
  to_bot: 'scout',
  summary: 'Collected the PD-1 affinity literature.',
  claims: [
    { statement: 'Binder A has a recorded KD of 4 nM', evidence_ref: 'result:9f1b', confidence: 'stated' },
    { statement: 'This target is druggable', evidence_ref: '', confidence: 'unsupported' },
  ],
  open_questions: ['Which ortholog?'],
  refs: ['reference:1'],
  produced_by_run: 'run-1',
  created_at: '2026-09-13T00:00:00Z',
}

function stub(items: unknown[]) {
  // The surface is project-scoped; without a project it correctly renders the
  // "pick one" line and none of these assertions would be about the record.
  useAppStore.setState({ activeProjectId: 'proj_test' })
  server.use(
    http.get('/api/v2/projects', () =>
      HttpResponse.json({
        items: [
          {
            id: 'proj_test',
            organization_id: 'org_test',
            name: 'Test project',
            project_type: 'protein_design',
            status: 'active',
            owner_id: 'user_test',
            summary: 'Chain test project',
            primary_target_id: null,
            version: 1,
            created_at: '2026-07-01T00:00:00Z',
            updated_at: '2026-07-01T00:00:00Z',
          },
        ],
        next_cursor: null,
      }),
    ),
    http.get('/api/v2/copilot/projects/:projectId/handoffs', () => HttpResponse.json({ items })),
    http.get('/api/v2/copilot/bots', () =>
      HttpResponse.json([
        {
          id: 'librarian',
          title: 'Librarian',
          title_zh: '文献整理',
          phase: 1,
          stance: 'produce',
          summary: 'Find and organise literature.',
          charter: 'Never summarise a paper you have not retrieved.',
          capabilities: ['research-read'],
          handoff: ['scout'],
          reviews: [],
          directs: [],
          reviewed_by: ['auditor'],
          triggers: ['literature'],
        },
        {
          id: 'scout',
          title: 'Scout',
          title_zh: '靶点情报',
          phase: 2,
          stance: 'produce',
          summary: 'Establish target identity.',
          charter: 'Never resolve an identifier by guessing from a name.',
          capabilities: ['project-read'],
          handoff: [],
          reviews: [],
          directs: [],
          reviewed_by: ['auditor'],
          triggers: ['target'],
        },
      ]),
    ),
  )
}

describe('CopilotChain', () => {
  it('names both operators and what was handed over', async () => {
    stub([HANDOFF])
    renderWithProviders(<CopilotChain />)

    expect(await screen.findByText('Collected the PD-1 affinity literature.')).toBeInTheDocument()
    expect(screen.getByText('Librarian')).toBeInTheDocument()
    expect(screen.getByText('Scout')).toBeInTheDocument()
  })

  it('says plainly which claims cite nothing', async () => {
    stub([HANDOFF])
    renderWithProviders(<CopilotChain />)

    expect(await screen.findByText('1 claim(s) here cite no evidence')).toBeInTheDocument()
    expect(screen.getByText('cites nothing')).toBeInTheDocument()
    // ...and the supported one still shows its reference rather than being
    // flattened to the same treatment.
    expect(screen.getByText('result:9f1b')).toBeInTheDocument()
  })

  it('shows what the operator could not settle', async () => {
    stub([HANDOFF])
    renderWithProviders(<CopilotChain />)

    expect(await screen.findByText('Which ortholog?')).toBeInTheDocument()
  })

  it('marks a note with no run behind it as unreviewable rather than clean', async () => {
    stub([{ ...HANDOFF, produced_by_run: null }])
    renderWithProviders(<CopilotChain />)

    expect(await screen.findByText('no transcript')).toBeInTheDocument()
  })

  it('moves the reader to the named successor', async () => {
    // Reading what was handed over and then hunting for the recipient in the
    // chat's dropdown is the handoff protocol working on paper only.
    const onSelectOperator = vi.fn()
    stub([HANDOFF])
    renderWithProviders(<CopilotChain onSelectOperator={onSelectOperator} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Scout' }))

    expect(onSelectOperator).toHaveBeenCalledWith('scout')
  })

  it('explains the empty chain instead of showing a blank panel', async () => {
    stub([])
    renderWithProviders(<CopilotChain />)

    expect(await screen.findByText('No handovers yet')).toBeInTheDocument()
  })

  it('renders a record whose optional lists are absent', async () => {
    // A row written before a field existed, or by a server that omits empties.
    // The generated types make these optional, and a crash here would take the
    // whole surface down for one malformed note.
    stub([{ id: 'h2', from_bot: 'librarian', to_bot: 'scout', summary: 'Bare note.', created_at: '2026-09-13T00:00:00Z' }])
    renderWithProviders(<CopilotChain />)

    expect(await screen.findByText('Bare note.')).toBeInTheDocument()
  })

  it('shows an unknown confidence rather than blanking it', async () => {
    // The server may be newer than this build; hiding the word would hide the
    // claim's standing with it.
    stub([
      {
        ...HANDOFF,
        claims: [{ statement: 's', evidence_ref: 'r', confidence: 'corroborated' }],
      },
    ])
    renderWithProviders(<CopilotChain />)

    expect(await screen.findByText('corroborated')).toBeInTheDocument()
  })
})
