import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { ProjectOverview } from '../../lib/api/projects'
import { renderWithProviders } from '../../test/renderWithProviders'
import { WorkflowProgress } from './WorkflowProgress'

afterEach(cleanup)

beforeEach(() => {
  window.location.hash = '/'
})

function overview(ready: boolean): ProjectOverview {
  return {
    project: {
      id: 'proj_test',
      organization_id: 'org_test',
      owner_id: 'user_test',
      name: 'Test target',
      project_type: 'binder_design',
      status: 'active',
      summary: null,
      prompt: null,
      primary_target_id: null,
      version: 1,
      created_at: '2026-07-01T00:00:00Z',
      updated_at: '2026-07-01T00:00:00Z',
    },
    funnel: { generated: 0, designed: 0, folded: 0, scored: 0, ordered: 0 },
    candidate_count: 0,
    experiment_result_count: 0,
    available_artifact_count: 0,
    active_job_count: 0,
    latest_workflow_id: null,
    next_action: ready ? 'Build workflow' : 'Confirm target identity',
    target_readiness: {
      stage: ready ? 'ready' : 'identity_confirmation',
      ready_for_workflow: ready,
      blockers: ready ? [] : ['target_identity_confirmation_required'],
      next_action: ready ? 'Build workflow' : 'Confirm target identity',
      target_id: null,
      structure_artifact_id: null,
      identity_status: null,
      structure_status: null,
    },
  }
}

function historicalOverview(): ProjectOverview {
  return {
    ...overview(false),
    funnel: { generated: 8, designed: 8, folded: 8, scored: 8, ordered: 3 },
    candidate_count: 8,
    experiment_result_count: 2,
  }
}

describe('WorkflowProgress', () => {
  it('exposes the workflow as controlled stepper tabs', () => {
    renderWithProviders(
      <WorkflowProgress projectQuery="?project=proj_test" overview={overview(true)} hasProject />,
    )

    expect(screen.getByRole('region', { name: /workflow progress/i })).toContainElement(
      screen.getByRole('tab', { name: /design/i }),
    )
  })

  it('connects every tab to a panel and navigates unlocked stages', () => {
    renderWithProviders(
      <WorkflowProgress projectQuery="?project=proj_test" overview={overview(true)} hasProject />,
    )

    for (const tab of screen.getAllByRole('tab')) {
      const panelId = tab.getAttribute('aria-controls')
      expect(panelId).toBeTruthy()
      expect(document.getElementById(panelId!)).toHaveAttribute('role', 'tabpanel')
    }

    fireEvent.click(screen.getByRole('tab', { name: /workflow/i }))
    expect(window.location.hash).toBe('#/workflow?project=proj_test')
  })

  it('keeps the screen-reader-only stepper panel within its containing block', () => {
    renderWithProviders(
      <WorkflowProgress projectQuery="?project=proj_test" overview={overview(true)} hasProject />,
    )

    expect(
      document.querySelector<HTMLElement>('[data-slot="stepper-panel"]'),
    ).toHaveClass('!w-px')
  })

  it('keeps the user in research while target readiness is blocked', () => {
    renderWithProviders(
      <WorkflowProgress projectQuery="?project=proj_test" overview={overview(false)} hasProject />,
    )

    expect(screen.getByRole('link', { name: 'Continue' })).toHaveAttribute(
      'href',
      '#/research?project=proj_test',
    )
    expect(screen.queryByRole('link', { name: 'Review' })).not.toBeInTheDocument()
  })

  it('unlocks workflow as the next step only after target readiness is complete', () => {
    renderWithProviders(
      <WorkflowProgress projectQuery="?project=proj_test" overview={overview(true)} hasProject />,
    )

    expect(screen.getByRole('link', { name: 'Continue' })).toHaveAttribute(
      'href',
      '#/workflow?project=proj_test',
    )
    expect(screen.getByRole('link', { name: 'Review' })).toHaveAttribute(
      'href',
      '#/research?project=proj_test',
    )
  })

  it('does not unlock the supported path from historical artifacts when readiness is blocked', () => {
    renderWithProviders(
      <WorkflowProgress
        projectQuery="?project=proj_test"
        overview={historicalOverview()}
        hasProject
      />,
    )

    expect(screen.getByRole('link', { name: 'Continue' })).toHaveAttribute(
      'href',
      '#/research?project=proj_test',
    )
    expect(screen.queryByRole('link', { name: 'Review' })).not.toBeInTheDocument()
  })
})
