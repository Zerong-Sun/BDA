import { useQuery } from '@tanstack/react-query'
import { getProjectTargetStructureOrNull, getTargetReadiness } from '../api/projects'

export function useProjectTargetStructure(projectId: string | null | undefined, enabled = true) {
  return useQuery({
    queryKey: ['project-target-structure', projectId],
    queryFn: () => getProjectTargetStructureOrNull(projectId!),
    enabled: Boolean(projectId) && enabled,
    staleTime: 60_000,
  })
}

export function useTargetReadiness(projectId: string | null | undefined) {
  return useQuery({
    queryKey: ['target-readiness', projectId],
    queryFn: () => getTargetReadiness(projectId!),
    enabled: Boolean(projectId),
    staleTime: 15_000,
  })
}
