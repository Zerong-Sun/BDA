import { useEffect, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getProject, listProjects } from '../api/projects'
import { useAppStore } from '../store/appStore'
import { currentAuthGeneration } from '../api/client'

// Keep view preferences, but never carry another project's evidence or draft.
const PROJECT_SELECTION_PARAMS = ['run', 'node', 'candidate', 'dataset', 'structureA', 'structureB', 'compare', 'artifact', 'residues', 'knowledge', 'goal', 'draft', 'draft_project', 'service', 'from', 'entry', 'campaign']

export function useProjectContext() {
  const sessionGeneration = useRef(currentAuthGeneration())
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
  // Historical sources have direct links but do not reappear in the portfolio.
  const lookupHistorical = Boolean(projectsReady && urlProjectId && !projectIds.has(urlProjectId) &&
    urlProjectId !== deletingProjectId && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(urlProjectId))
  const historicalQuery = useQuery({
    queryKey: ['historical-project', currentAuthGeneration(), urlProjectId],
    queryFn: () => getProject(urlProjectId!),
    enabled: lookupHistorical,
    retry: false,
    staleTime: 30_000,
  })
  const historyLink = historicalQuery.data?.localized_content?.portfolio_consolidation
  const historicalProject = lookupHistorical && historyLink && typeof historyLink === 'object' &&
    'role' in historyLink && historyLink.role === 'historical_source' &&
    'canonical_project_id' in historyLink && typeof historyLink.canonical_project_id === 'string' &&
    projectIds.has(historyLink.canonical_project_id) && historicalQuery.data?.id === urlProjectId
    ? historicalQuery.data : null
  const waitingHistorical = lookupHistorical && historicalQuery.isPending
  const staleUrlProject = Boolean(projectsReady && !waitingHistorical && urlProjectId && !projectIds.has(urlProjectId) && !historicalProject)
  const staleActiveProject = Boolean(projectsReady && !waitingHistorical && activeProjectId &&
    !projectIds.has(activeProjectId) && historicalProject?.id !== activeProjectId)

  const projectId = useMemo(() => {
    if (urlProjectId) return projectIds.has(urlProjectId) || historicalProject ? urlProjectId : ''
    if (activeProjectId && projectIds.has(activeProjectId)) return activeProjectId
    return ''
  }, [activeProjectId, projectIds, urlProjectId, historicalProject])

  useEffect(() => {
    // A still-mounted view must not restore its old URL selection after logout.
    if (sessionGeneration.current !== currentAuthGeneration()) return
    if (projectsLoading || !projectId) return
    if (activeProjectId !== projectId) setActiveProjectId(projectId)
  }, [activeProjectId, projectId, projectsLoading, setActiveProjectId])

  useEffect(() => {
    if (sessionGeneration.current !== currentAuthGeneration()) return
    if (!projectsReady) return
    if (!staleUrlProject && !staleActiveProject) return
    if (staleUrlProject || (staleActiveProject && !projectId)) setActiveProjectId('')
    if (staleUrlProject) {
      const next = new URLSearchParams(searchParams)
      next.delete('project')
      for (const key of PROJECT_SELECTION_PARAMS) next.delete(key)
      if (next.toString() !== searchParams.toString()) setSearchParams(next, { replace: true })
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

  const activeProject = visibleProjects.find((p) => p.id === projectId) ?? historicalProject

  const setProjectId = (nextProjectId: string) => {
    setActiveProjectId(nextProjectId)
    const next = new URLSearchParams(searchParams)
    if (nextProjectId !== projectId) {
      for (const key of PROJECT_SELECTION_PARAMS) next.delete(key)
    }
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
    projectsLoading: projectsLoading || waitingHistorical,
    projectsError,
    projectsQueryError,
    refetchProjects,
    setProjectId,
    hasStaleProjectReference: staleUrlProject || staleActiveProject,
    hasProject: Boolean(activeProject),
  }
}
