import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listProjects } from '../api/projects'
import { useAppStore } from '../store/appStore'

export function useProjectContext() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const deletingProjectId = useAppStore((state) => state.deletingProjectId)
  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)

  const {
    data: projects = [],
    isLoading: projectsLoading,
    isError: projectsError,
    error: projectsQueryError,
    refetch: refetchProjects,
  } = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
    staleTime: 30_000,
  })

  const sortedProjects = useMemo(() => {
    const priority = (project: (typeof projects)[number]) => {
      if (project.status === 'running') return 0
      if (project.status === 'active') return 1
      return 2
    }
    return [...projects].sort(
      (a, b) =>
        priority(a) - priority(b) || a.name.localeCompare(b.name),
    )
  }, [projects])

  const visibleProjects = useMemo(
    () =>
      sortedProjects.filter(
        (project) =>
          project.status !== 'trashed' && project.id !== deletingProjectId,
      ),
    [deletingProjectId, sortedProjects],
  )

  const projectIds = useMemo(() => new Set(visibleProjects.map((project) => project.id)), [visibleProjects])
  const urlProjectId = searchParams.get('project')
  const projectsReady = !projectsLoading && !projectsError
  const staleUrlProject = Boolean(projectsReady && urlProjectId && !projectIds.has(urlProjectId))
  const staleActiveProject = Boolean(projectsReady && activeProjectId && !projectIds.has(activeProjectId))

  const projectId = useMemo(() => {
    if (urlProjectId && projectIds.has(urlProjectId)) return urlProjectId
    if (activeProjectId && projectIds.has(activeProjectId)) return activeProjectId
    return ''
  }, [activeProjectId, projectIds, urlProjectId])

  useEffect(() => {
    if (projectsLoading || !projectId) return
    if (activeProjectId !== projectId) setActiveProjectId(projectId)
  }, [activeProjectId, projectId, projectsLoading, setActiveProjectId])

  useEffect(() => {
    if (!projectsReady) return
    if (!staleUrlProject && !staleActiveProject) return
    if (staleActiveProject && !projectId) setActiveProjectId('')
    if (staleUrlProject) {
      const next = new URLSearchParams(searchParams)
      next.delete('project')
      setSearchParams(next, { replace: true })
    }
  }, [
    projectId,
    projectsReady,
    searchParams,
    setActiveProjectId,
    setSearchParams,
    staleActiveProject,
    staleUrlProject,
  ])

  const activeProject = visibleProjects.find((p) => p.id === projectId) ?? null

  const setProjectId = (nextProjectId: string) => {
    setActiveProjectId(nextProjectId)
    const next = new URLSearchParams(searchParams)
    if (nextProjectId) next.set('project', nextProjectId)
    else next.delete('project')
    setSearchParams(next)
  }

  return {
    projectId,
    activeProject,
    projects: sortedProjects,
    visibleProjects,
    deletingProjectId,
    projectsLoading,
    projectsError,
    projectsQueryError,
    refetchProjects,
    setProjectId,
    hasStaleProjectReference: staleUrlProject || staleActiveProject,
    hasProject: Boolean(activeProject),
  }
}
