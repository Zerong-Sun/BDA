import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { RecordDecisionButton } from './RecordDecisionButton'
import { seededDraft } from './timelineEntryForm'

/**
 * Recording a decision from where the work happened.
 *
 * The measured failure this addresses: 97 rulings in a Markdown file, 8 rows in the table,
 * and `provenance` holding 49 cluster job numbers as strings and no addressable object.
 * Rationale that costs a separate act to capture does not get captured - so the act moves
 * to where the ids already are.
 *
 * The other half is what is *not* seeded. A prefilled conclusion would be a machine's
 * opinion carrying a person's signature, in the one record whose purpose is to say whose
 * judgement a thing was.
 */

afterEach(cleanup)

describe('seededDraft', () => {
  it('carries the ids the caller already had into provenance', () => {
    const draft = seededDraft({
      lane: 'dry',
      provenance: { job_ids: ['job-1', 'job-2'], external_refs: ['lsf:4180231'] },
    })
    expect(draft.provenance.job_ids).toBe('job-1\njob-2')
    expect(draft.provenance.external_refs).toBe('lsf:4180231')
    expect(draft.lane).toBe('dry')
  })

  it('leaves the judgement empty', () => {
    // Title, conclusion and the rejected branch are the researcher's. Filling them would
    // put a model's opinion under a person's name in the record that exists to say whose
    // judgement it was.
    const draft = seededDraft({ provenance: { job_ids: ['job-1'] } })
    expect(draft.title).toBe('')
    expect(draft.outcome).toBe('unspecified')
    expect(draft.alternatives).toEqual([])
    expect(draft.decision_ref).toBe('')
  })

  it('ignores an empty id list rather than writing a blank citation', () => {
    const draft = seededDraft({ provenance: { candidate_ids: [] } })
    expect(draft.provenance.candidate_ids).toBe('')
  })
})

describe('RecordDecisionButton', () => {
  it('opens an editor with the evidence already cited', async () => {
    server.use(
      http.get('/api/v2/jobs', () =>
        HttpResponse.json({
          items: [{ id: 'job-1', external_id: 'lsf-9001', status: 'succeeded' }],
          next_cursor: null,
        }),
      ),
    )
    renderWithProviders(
      <RecordDecisionButton projectId="p1" seed={{ lane: 'dry', provenance: { job_ids: ['job-1'] } }} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /record a decision/i }))
    // The job arrives cited: the picker shows it selected, not waiting to be found again.
    const checkbox = await screen.findByRole('checkbox', { name: /lsf-9001/i })
    expect(checkbox).toBeChecked()
  })

  it('does not open an editor until asked', () => {
    renderWithProviders(<RecordDecisionButton projectId="p1" seed={{}} />)
    expect(screen.queryByLabelText(/Title/)).not.toBeInTheDocument()
  })
})

describe('where the editor renders', () => {
  it('opens in a dialog, not inside whatever row the button sits in', async () => {
    // The editor is a full two-column form written for a page column. Inline it lands in
    // a results-table cell or a narrow job drawer - which is exactly where this button is
    // useful and where that layout is not.
    server.use(
      http.get('/api/v2/jobs', () => HttpResponse.json({ items: [], next_cursor: null })),
    )
    renderWithProviders(<RecordDecisionButton projectId="p1" seed={{ lane: 'dry' }} />)

    fireEvent.click(screen.getByRole('button', { name: /record a decision/i }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toBeInTheDocument()
    expect(await within(dialog).findByLabelText(/Title/)).toBeInTheDocument()
  })
})
