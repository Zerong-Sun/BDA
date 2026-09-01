import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { DesignPromptCard } from './DesignPromptCard'
import type { Project } from '../../lib/schemas/project'

const { createProjectPromptDraft, waitForProjectPromptDraft, updateProjectPrompt } = vi.hoisted(() => ({
  createProjectPromptDraft: vi.fn(),
  waitForProjectPromptDraft: vi.fn(),
  updateProjectPrompt: vi.fn(),
}))

vi.mock('../../lib/api/projects', () => ({ createProjectPromptDraft, waitForProjectPromptDraft, updateProjectPrompt }))

const baseProject: Project = {
  id: 'proj_test',
  organization_id: 'org_test',
  owner_id: 'user_test',
  name: 'Test project',
  project_type: 'protein_design',
  summary: null,
  prompt: 'Design a high-affinity binder against the stated target.',
  status: 'active',
  primary_target_id: null,
  version: 1,
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

beforeEach(() => {
  createProjectPromptDraft.mockReset()
  waitForProjectPromptDraft.mockReset()
  updateProjectPrompt.mockReset()
})

afterEach(cleanup)

describe('DesignPromptCard', () => {
  it('offers to generate a prompt when the project has none yet', () => {
    renderWithProviders(<DesignPromptCard project={{ ...baseProject, prompt: null }} />)
    expect(screen.getByRole('button', { name: /generate design prompt/i })).toBeInTheDocument()
  })

  it('reveals the prompt text after the show toggle is clicked', () => {
    renderWithProviders(<DesignPromptCard project={baseProject} />)
    expect(screen.queryByText(baseProject.prompt as string)).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /show/i }))
    expect(screen.getByText(baseProject.prompt as string)).toBeInTheDocument()
  })

  it('edits, regenerates, and saves the prompt', async () => {
    createProjectPromptDraft.mockResolvedValue({ draft_id: 'draft_1' })
    waitForProjectPromptDraft.mockResolvedValue({ id: 'draft_1', status: 'ready', prompt: 'Regenerated prompt.', error: null })
    updateProjectPrompt.mockResolvedValue({ ...baseProject, prompt: 'Regenerated prompt.', version: 2 })

    renderWithProviders(<DesignPromptCard project={baseProject} />)
    fireEvent.click(screen.getByRole('button', { name: /^edit$/i }))

    const textarea = screen.getByLabelText('Design prompt') as HTMLTextAreaElement
    expect(textarea).toHaveValue(baseProject.prompt)

    fireEvent.click(screen.getByRole('button', { name: /regenerate/i }))
    await waitFor(() => expect(textarea).toHaveValue('Regenerated prompt.'))

    // The prompt is what the goal tree was derived from, so rewriting it costs a
    // sentence: the server refuses the change without one, and asking here beats
    // surfacing a 422 after the person has stopped thinking about why they edited.
    fireEvent.change(screen.getByLabelText(/why is the prompt changing/i), {
      target: { value: 'narrowing to single chain' },
    })

    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() =>
      expect(updateProjectPrompt).toHaveBeenCalledWith(
        'proj_test',
        'Regenerated prompt.',
        1,
        'narrowing to single chain',
      ),
    )
    await waitFor(() => expect(screen.queryByLabelText('Design prompt')).not.toBeInTheDocument())
  })

  it('will not save a changed prompt until a reason is given', () => {
    renderWithProviders(<DesignPromptCard project={baseProject} />)
    fireEvent.click(screen.getByRole('button', { name: /^edit$/i }))

    fireEvent.change(screen.getByLabelText('Design prompt'), { target: { value: 'Something else entirely.' } })
    expect(screen.getByRole('button', { name: /^save$/i })).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/why is the prompt changing/i), { target: { value: 'because' } })
    expect(screen.getByRole('button', { name: /^save$/i })).toBeEnabled()
  })

  it('does not demand a reason for re-saving the same text', () => {
    // A form that round-trips the whole object is not a change and must not be treated
    // as one; the server applies the same rule.
    renderWithProviders(<DesignPromptCard project={baseProject} />)
    fireEvent.click(screen.getByRole('button', { name: /^edit$/i }))
    expect(screen.getByRole('button', { name: /^save$/i })).toBeEnabled()
  })

  it('asks for no reason when the project is getting its first prompt', () => {
    renderWithProviders(<DesignPromptCard project={{ ...baseProject, prompt: null }} />)
    fireEvent.click(screen.getByRole('button', { name: /generate design prompt/i }))
    expect(screen.queryByLabelText(/why is the prompt changing/i)).not.toBeInTheDocument()
  })
})
