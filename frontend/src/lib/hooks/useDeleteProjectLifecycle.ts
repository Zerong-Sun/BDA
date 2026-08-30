import { useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { deleteProject, type Project } from '../api/projects'
import { useAppStore } from '../store/appStore'
import { useProjectContext } from './useProjectContext'

function currentUrlProjectId() {
  if (typeof window === 'undefined') return null
  const hashQuery = window.location.hash.split('?')[1] ?? ''
  const search = hashQuery || window.location.search.replace(/^\?/, '')
  return new URLSearchParams(search).get('project')
}

function redirectToProjects() {
  if (typeof window === 'undefined') return
  window.location.hash = '/experiments'
}

function redirectToProjectsAfterContextCleanup() {
  if (typeof window === 'undefined') return
  window.setTimeout(redirectToProjects, 0)
}

export const DELETE_PROJECT_CONFIRMATION =
  'Move "{projectName}" to project trash?\n\nThe project is soft-deleted for the configured retention period. Artifacts remain in MinIO until a maintenance purge runs.'

export function invalidateDeletedProjectQueries(queryClient: QueryClient, projectId: string) {
  queryClient.removeQueries({
    predicate: ({ queryKey }) => queryKey.some((part) => part === projectId),
  })
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ['projects'] }),
  ])
}

export function useDeleteProjectLifecycle() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const clearProjectState = useAppStore((state) => state.clearProjectState)
  const setDeletingProjectId = useAppStore((state) => state.setDeletingProjectId)
  const { projectId, setProjectId } = useProjectContext()

  const mutation = useMutation({
    mutationFn: (deleteProjectId: string) => deleteProject(deleteProjectId),
    onMutate: (deleteProjectId) => {
      setDeletingProjectId(deleteProjectId)
      queryClient.setQueryData<Project[]>(['projects'], (current) =>
        Array.isArray(current)
          ? current.filter((project) => project.id !== deleteProjectId)
          : current,
      )
    },
    onSuccess: async (_result, deletedProjectId) => {
      const wasCurrentProject =
        projectId === deletedProjectId ||
        activeProjectId === deletedProjectId ||
        currentUrlProjectId() === deletedProjectId
      queryClient.setQueryData<Project[]>(['projects'], (current) =>
        Array.isArray(current)
          ? current.filter((project) => project.id !== deletedProjectId)
          : current,
      )
      clearProjectState(deletedProjectId)
      if (wasCurrentProject) {
        setProjectId('')
      }
      navigate('/experiments', { replace: true })
      await invalidateDeletedProjectQueries(queryClient, deletedProjectId)
      redirectToProjectsAfterContextCleanup()
    },
    onSettled: () => {
      setDeletingProjectId(null)
    },
  })

  const confirmAndDeleteProject = (project: Project) => {
    const ok = window.confirm(
      DELETE_PROJECT_CONFIRMATION.replace('{projectName}', project.name),
    )
    if (ok) mutation.mutate(project.id)
  }

  return {
    ...mutation,
    confirmAndDeleteProject,
    deletingProjectId: mutation.variables ?? null,
  }
}
