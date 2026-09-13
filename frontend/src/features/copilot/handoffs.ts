import { useQuery } from '@tanstack/react-query'
import { listHandoffsApiV2CopilotProjectsProjectIdHandoffsGet } from '../../lib/api/generated'

/**
 * Reading the chain's handover record.
 *
 * Its own module rather than living beside the view, because this repository
 * requires a component file to export only components - fast refresh replaces a
 * module wholesale, and a hook exported from the same file loses its state on
 * every edit to the markup around it. `bots/registry.ts` is the same split for
 * the same reason.
 */

/**
 * Exported so a turn that records a handover can make the Chain tab show it.
 *
 * Without a consumer this was a key nobody could invalidate, which mattered less
 * than it looks - the query sets no `staleTime`, so opening the tab refetches -
 * but it meant a Chain tab left open while the conversation continued kept
 * showing a chain that had moved on.
 */
export const copilotHandoffsQueryKey = (projectId: string | null) =>
  ['copilot', 'handoffs', projectId] as const

export function useCopilotHandoffs(projectId: string | null) {
  return useQuery({
    // The project id is in the key because a handover belongs to one project and
    // nothing else; a shared key would show one project's chain inside another.
    queryKey: copilotHandoffsQueryKey(projectId),
    enabled: Boolean(projectId),
    queryFn: async () => {
      const { data } = await listHandoffsApiV2CopilotProjectsProjectIdHandoffsGet<true>({
        throwOnError: true,
        path: { project_id: projectId as string },
      })
      return data.items
    },
  })
}
