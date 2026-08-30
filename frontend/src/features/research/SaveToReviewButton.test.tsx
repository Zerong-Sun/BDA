import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { server } from '../../test/mocks/handlers'
import { useAppStore } from '../../lib/store/appStore'
import { SaveToReviewButton } from './SaveToReviewButton'

describe('SaveToReviewButton', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
    server.use(
      http.post('/api/v2/projects/proj_test/research-findings', async ({ request }) => {
        const body = await request.json()
        return HttpResponse.json({ data: body, trace_id: 'test' })
      }),
    )
  })

  afterEach(() => {
    cleanup()
  })

  it('saves directly when review track is known', async () => {
    renderWithProviders(
      <SaveToReviewButton
        projectId="proj_test"
        content="## Binder interface\nSupports wet-lab follow-up."
        reviewTrack="binding_strategy"
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Save to project review' }))

    await waitFor(() => {
      expect(useAppStore.getState().language).toBe('en')
      expect(screen.queryByText('Could not save to the project review.')).not.toBeInTheDocument()
    })
  })

  it('opens section picker when only review intent is known', async () => {
    renderWithProviders(
      <SaveToReviewButton
        projectId="proj_test"
        content="Draft review paragraph"
        reviewIntent
        userPrompt="请完善项目的纯化方案"
      />,
    )

    const trigger = screen.getByRole('button', { name: 'Save to project review' })
    trigger.focus()
    expect(trigger).toHaveAttribute('data-slot', 'popover-trigger')
    fireEvent.click(trigger)
    expect(screen.getByText('Pick section')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Expression and purification plan' })).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByText('Pick section')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })

  it('stays hidden for unrelated assistant replies', () => {
    const { container } = renderWithProviders(
      <SaveToReviewButton
        projectId="proj_test"
        content="Candidate ranking explanation"
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
