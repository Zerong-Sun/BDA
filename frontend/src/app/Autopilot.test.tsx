import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../test/mocks/handlers'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import { AutopilotPage } from './Autopilot'

/**
 * The stage list, and the one control that can finish a campaign.
 *
 * Some stages have no automatic product by design - `review` is somebody's
 * judgement - and `release` refuses anything that is not held. So a chain that
 * reached one had no action available anywhere, and the default campaign ends
 * with `review`. "Mark this stage done" is the verb that was missing, which
 * makes it worth a test: it is the only way a campaign ever ends.
 */

afterEach(cleanup)

const PROJECT_ID = 'proj_test'

function stage(overrides: Record<string, unknown> = {}) {
  return {
    id: 'stage_review',
    stage_key: 'review',
    position: 0,
    status: 'ready',
    risk_tier: 'reversible_draft',
    held: false,
    released_at: null,
    released_by: null,
    hold_reason: null,
    operator: null,
    operator_reason: "stage 'review' has no operator: a review stage is a person's judgement",
    version: 1,
    resource_type: null,
    resource_id: null,
    ...overrides,
  }
}

function campaign(stages: Record<string, unknown>[]) {
  return {
    id: 'camp_1',
    project_id: PROJECT_ID,
    draft_id: 'draft_1',
    manual_campaign_id: null,
    name: 'PD-1 campaign',
    autonomy: 'supervised',
    status: 'running',
    frozen_prompt: 'Find PD-1 binders',
    frozen_spec: {},
    started_at: null,
    cancelled_at: null,
    taken_over_at: null,
    taken_over_by: null,
    stages,
    version: 1,
    created_at: '2026-09-13T00:00:00Z',
    updated_at: '2026-09-13T00:00:00Z',
  }
}

/** Drive the page to a confirmed campaign, which is the only way it holds one. */
async function withCampaign(stages: Record<string, unknown>[]) {
  useAppStore.setState({ activeProjectId: PROJECT_ID, language: 'en' })
  server.use(
    http.get('/api/v2/projects', () =>
      HttpResponse.json({
        items: [
          {
            id: PROJECT_ID,
            organization_id: 'org_test',
            name: 'Test project',
            project_type: 'protein_design',
            status: 'active',
            owner_id: 'user_test',
            summary: 'Autopilot test project',
            primary_target_id: null,
            version: 1,
            created_at: '2026-07-01T00:00:00Z',
            updated_at: '2026-07-01T00:00:00Z',
          },
        ],
        next_cursor: null,
      }),
    ),
    http.post('/api/v2/autopilot-drafts', () =>
      HttpResponse.json(
        {
          id: 'draft_1',
          project_id: PROJECT_ID,
          prompt: 'Find PD-1 binders',
          structured_brief: {},
          normalized_spec: { stages: ['review'] },
          status: 'ready',
          confirmed_campaign_id: null,
          version: 1,
          created_at: '2026-09-13T00:00:00Z',
          updated_at: '2026-09-13T00:00:00Z',
        },
        { status: 201, headers: { ETag: 'W/"1"' } },
      ),
    ),
    http.post('/api/v2/autopilot-drafts/draft_1/confirm', () =>
      HttpResponse.json(campaign(stages), { status: 201, headers: { ETag: 'W/"1"' } }),
    ),
  )

  renderWithProviders(<AutopilotPage />)

  fireEvent.change(
    await screen.findByPlaceholderText(
      'Describe objectives, constraints, success criteria, and stages…',
    ),
    { target: { value: 'Find PD-1 binders and review what comes back' } },
  )
  fireEvent.click(screen.getByRole('button', { name: 'Generate structured preview' }))
  fireEvent.change(await screen.findByLabelText('Campaign name'), {
    target: { value: 'PD-1 campaign' },
  })
  fireEvent.change(screen.getByLabelText('GPU-hour hard limit'), { target: { value: '1' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm immutable campaign' }))
  // Wait on the key this campaign actually declares, not a fixed one: the
  // helper is reused for `submit` and `research` stages too.
  await screen.findByText(String(stages[0].stage_key ?? 'review'))
}

describe('Autopilot stages', () => {
  it('offers a way to finish a human step', async () => {
    await withCampaign([stage()])

    expect(
      await screen.findByRole('button', { name: 'Mark this stage done' }),
    ).toBeInTheDocument()
  })

  it('does not offer it before the step has started', async () => {
    // `pending` is not somebody's turn yet; a control here would invite a
    // signature on work that has not begun.
    await withCampaign([stage({ status: 'pending' })])

    expect(screen.queryByRole('button', { name: 'Mark this stage done' })).not.toBeInTheDocument()
  })

  it('does not offer it for a stage whose product settles it', async () => {
    // An agent run ends its own stage. A second answer to "how did this end"
    // would let somebody mark it done while its operator is still writing.
    await withCampaign([
      stage({ resource_type: 'copilot_agent_run', resource_id: 'run_1', operator: 'librarian' }),
    ])

    expect(screen.queryByRole('button', { name: 'Mark this stage done' })).not.toBeInTheDocument()
  })

  it('offers it for a workflow draft, which is handed over rather than reporting back', async () => {
    // The adapter creates a draft for somebody to open in the Workflow page and
    // finish, so the person who finished it is the one who can say the step is
    // over. Refusing every product left a compute stage unfinishable - the same
    // dead end `review` had one stage earlier.
    await withCampaign([
      stage({
        stage_key: 'compute',
        resource_type: 'workflow_run',
        resource_id: 'wf_1',
        operator: 'planner',
      }),
    ])

    expect(await screen.findByRole('link', { name: 'Open in Workflow' })).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: 'Mark this stage done' }),
    ).toBeInTheDocument()
  })

  it('offers release rather than completion for a held stage', async () => {
    // Two different questions: *may this act* and *is this done*.
    await withCampaign([
      stage({
        stage_key: 'submit',
        risk_tier: 'spends_budget',
        held: true,
        hold_reason: "stage 'submit' commits budget or submits work",
      }),
    ])

    expect(await screen.findByRole('button', { name: 'Release this stage' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark this stage done' })).not.toBeInTheDocument()
  })

  it('sends the stage version so a stale tab cannot complete twice', async () => {
    let seen: string | null = null
    await withCampaign([stage({ version: 7 })])
    server.use(
      http.post('/api/v2/autopilot-campaigns/camp_1/stages/stage_review/complete', ({ request }) => {
        seen = request.headers.get('If-Match')
        return HttpResponse.json(stage({ status: 'succeeded', version: 8 }), {
          headers: { ETag: 'W/"8"' },
        })
      }),
      http.get('/api/v2/autopilot-campaigns/camp_1', () =>
        HttpResponse.json(campaign([stage({ status: 'succeeded', version: 8 })])),
      ),
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Mark this stage done' }))

    await waitFor(() => expect(seen).toBe('W/"7"'))
  })

  it('names the operator accountable for a stage', async () => {
    await withCampaign([stage({ operator: 'librarian', stage_key: 'research' })])

    expect(await screen.findByText('· librarian')).toBeInTheDocument()
  })

  it('says a stage has no operator rather than leaving it blank', async () => {
    // A stage attributed to nobody with no explanation reads as an oversight
    // rather than as the decision it is.
    await withCampaign([stage()])

    expect(await screen.findByText('· no operator')).toBeInTheDocument()
  })
})
