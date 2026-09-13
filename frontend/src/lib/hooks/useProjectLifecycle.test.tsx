import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { server } from '../../test/mocks/handlers'
import type { Project } from '../api/projects'
import { useAppStore } from '../store/appStore'
import { useDeleteProjectLifecycle } from './useDeleteProjectLifecycle'
import { useProjectContext } from './useProjectContext'
import { Button } from '../../components/ui/Button'

function makeProject(projectId: string): Project {
  return {
    id: projectId,
    organization_id: 'org_test',
    name: `Project ${projectId}`,
    project_type: 'protein_design',
    status: 'active',
    owner_id: 'user_test',
    summary: 'Lifecycle test project',
    prompt: null,
    primary_target_id: null,
    version: 1,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  }
}

function mockProjectList(projects: Project[]) {
  server.use(
    http.get('/api/v2/projects', () =>
      HttpResponse.json({
        items: projects,
        next_cursor: null,
      }),
    ),
  )
}

function ProjectContextProbe() {
  const { hasStaleProjectReference, projectId } = useProjectContext()
  return (
    <div>
      <span data-testid="project-id">{projectId || 'none'}</span>
      <span data-testid="stale-project">
        {hasStaleProjectReference ? 'stale' : 'fresh'}
      </span>
    </div>
  )
}

function DeleteProjectProbe() {
  const { visibleProjects } = useProjectContext()
  const projectDelete = useDeleteProjectLifecycle()
  const project = visibleProjects[0] ?? null
  return (
    <button
      type="button"
      disabled={!project || projectDelete.isPending}
      onClick={() => project && projectDelete.confirmAndDeleteProject(project)}
    >
      Move to trash
    </button>
  )
}

function DeleteProjectRoutes() {
  return (
    <Routes>
      <Route path="/workflow" element={<DeleteProjectProbe />} />
      <Route path="/experiments" element={<span data-testid="projects-route">Projects</span>} />
    </Routes>
  )
}

describe('project lifecycle hooks', () => {
  it('drops the old run and structure selection when selecting another project', async () => {
    mockProjectList([makeProject('a'), makeProject('b')])
    window.location.hash = '/bots?project=a&view=tasks&run=old&structureA=old-a&structureB=old-b&compare=1'
    function SwitchProject() {
      const { projectId, setProjectId } = useProjectContext()
      return <Button type="button" disabled={!projectId} onClick={() => setProjectId('b')}>Switch project</Button>
    }
    renderWithProviders(<SwitchProject />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Switch project' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Switch project' }))
    expect(window.location.hash).toBe('#/bots?project=b&view=tasks')
  })
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    window.location.hash = '/'
    useAppStore.setState({
      activeProjectId: '',
    })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('self-heals stale URL and persisted active project references', async () => {
    mockProjectList([makeProject('proj_live')])
    useAppStore.setState({ activeProjectId: 'proj_missing' })
    window.location.hash = '/workflow?project=proj_missing'

    renderWithProviders(<ProjectContextProbe />)

    await waitFor(() => expect(screen.getByTestId('stale-project')).toHaveTextContent('stale'))
    expect(screen.getByTestId('project-id')).toHaveTextContent('none')
    expect(useAppStore.getState().activeProjectId).toBe('')
    expect(window.location.hash).not.toContain('project=proj_missing')
  })

  it('clears current project state and URL when a project is moved to trash', async () => {
    mockProjectList([makeProject('proj_delete_test')])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    useAppStore.setState({
      activeProjectId: 'proj_delete_test',
    })
    window.location.hash = '/workflow?project=proj_delete_test'

    renderWithProviders(<DeleteProjectRoutes />)

    const deleteButton = await screen.findByRole('button', { name: 'Move to trash' })
    await waitFor(() => expect(deleteButton).not.toBeDisabled())
    fireEvent.click(deleteButton)

    await waitFor(() => expect(useAppStore.getState().activeProjectId).toBe(''))
    await waitFor(() => expect(window.location.hash).toContain('/experiments'))
    expect(window.location.hash).not.toContain('project=proj_delete_test')
  })

  it('removes deleted project from visibleProjects immediately', async () => {
    mockProjectList([makeProject('proj_delete_test'), makeProject('proj_keep')])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    useAppStore.setState({ activeProjectId: 'proj_keep' })

    function VisibleProjectsProbe() {
      const { visibleProjects } = useProjectContext()
      const projectDelete = useDeleteProjectLifecycle()
      const target = visibleProjects.find((p) => p.id === 'proj_delete_test')
      return (
        <div>
          <span data-testid="visible-count">{visibleProjects.length}</span>
          <button
            type="button"
            disabled={!target}
            onClick={() => target && projectDelete.confirmAndDeleteProject(target)}
          >
            Delete test project
          </button>
        </div>
      )
    }

    renderWithProviders(<VisibleProjectsProbe />)

    await waitFor(() => expect(screen.getByTestId('visible-count')).toHaveTextContent('2'))
    fireEvent.click(screen.getByRole('button', { name: 'Delete test project' }))

    await waitFor(() => expect(screen.getByTestId('visible-count')).toHaveTextContent('1'))
    expect(screen.queryByText('Project proj_delete_test')).not.toBeInTheDocument()
  })
})
