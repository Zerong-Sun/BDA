import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ProjectChooser } from './ProjectChooser'

const { setProjectId, createProject, createProjectPromptDraft, waitForProjectPromptDraft, deleteProject } = vi.hoisted(() => ({
  setProjectId: vi.fn(),
  createProject: vi.fn(),
  createProjectPromptDraft: vi.fn(),
  waitForProjectPromptDraft: vi.fn(),
  deleteProject: vi.fn(),
}))

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({
    visibleProjects: [
      {
        id: 'proj_test',
        organization_id: 'org_test',
        owner_id: 'user_test',
        name: 'Test project',
        project_type: 'protein_design',
        summary: null,
        status: 'active',
        primary_target_id: null,
        version: 1,
        created_at: '2026-07-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:00Z',
      },
    ],
    projectId: 'proj_test',
    setProjectId,
  }),
}))

vi.mock('../../lib/api/projects', () => ({ createProject, createProjectPromptDraft, waitForProjectPromptDraft, deleteProject }))

beforeEach(() => {
  setProjectId.mockReset()
  createProject.mockReset()
  createProjectPromptDraft.mockReset()
  waitForProjectPromptDraft.mockReset()
  useAppStore.setState({ appMode: 'application', language: 'en' })
})

afterEach(cleanup)

describe('ProjectChooser', () => {
  it('clears a selected project through the localized sentinel option', () => {
    renderWithProviders(<ProjectChooser />)

    fireEvent.click(screen.getByRole('combobox', { name: /select research project/i }))
    const clearOption = screen.getByRole('option', { name: 'No project' })
    fireEvent.pointerDown(clearOption, { button: 0 })
    fireEvent.pointerUp(clearOption, { button: 0 })
    fireEvent.click(clearOption)

    expect(setProjectId).toHaveBeenCalledWith('')
  })

  it('keeps create disabled until a design prompt has been generated, then submits it', async () => {
    createProjectPromptDraft.mockResolvedValue({ draft_id: 'draft_1' })
    waitForProjectPromptDraft.mockResolvedValue({ id: 'draft_1', status: 'ready', prompt: 'Generated design prompt.', error: null })
    createProject.mockResolvedValue({ id: 'proj_new' })

    renderWithProviders(<ProjectChooser />)
    fireEvent.click(screen.getByRole('button', { name: /create project/i }))

    const createButton = screen.getByRole('button', { name: /create and select/i })
    expect(createButton).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/project name/i), { target: { value: 'New project' } })
    expect(createButton).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: /generate design prompt/i }))
    await waitFor(() => expect(screen.getByLabelText(/design prompt/i)).toHaveValue('Generated design prompt.'))
    expect(createButton).toBeEnabled()

    fireEvent.click(createButton)
    await waitFor(() => expect(createProject).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'New project', prompt: 'Generated design prompt.' }),
    ))
  })
})
