import { useQuery } from '@tanstack/react-query'
import { getProjectAccess, type ProjectAccess } from '../api/projects'

/**
 * The signed-in user's effective role in one project, as the server computes it.
 *
 * Only ever used to hide or disable controls: the server authorizes every action
 * itself, so a stale or missing answer can make the UI more permissive than the
 * server for a moment but never let an action through. The role changes rarely,
 * so it is not refetched per view.
 */
export function useProjectAccess(projectId: string | null | undefined) {
  return useQuery<ProjectAccess>({
    queryKey: ['project-access', projectId],
    queryFn: () => getProjectAccess(projectId as string),
    enabled: Boolean(projectId),
    staleTime: 5 * 60 * 1000,
  })
}

const MANAGING_ROLES = new Set(['admin', 'owner'])

/** Whether this role manages the project (model settings, membership). */
export function managesProject(access: ProjectAccess | undefined): boolean {
  return Boolean(access && MANAGING_ROLES.has(access.role))
}
