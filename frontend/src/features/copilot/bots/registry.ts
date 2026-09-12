import { useQuery } from '@tanstack/react-query'
import type { BotResponse } from '../../../lib/api/generated'
import { listBotsApiV2CopilotBotsGet } from '../../../lib/api/generated'

/**
 * The roster comes from `/copilot/bots`. Nothing here restates which
 * capabilities a bot holds.
 *
 * The skills registry this sits beside kept its own copy of the backend's
 * capability list, and the copy is what drifts: a capability renamed on the
 * server left a trigger list pointing at an id the API would reject. Matching
 * against the served roster cannot drift, because there is only one roster.
 *
 * Matching is a suggestion either way. The backend intersects whatever bot the
 * client names with the project's enabled capabilities, so a wrong suggestion
 * costs a narrower turn and never a wider one.
 */

export type CopilotBot = BotResponse

export const copilotBotsQueryKey = ['copilot', 'bots'] as const

export function useCopilotBots() {
  return useQuery({
    queryKey: copilotBotsQueryKey,
    queryFn: async () => {
      const { data } = await listBotsApiV2CopilotBotsGet<true>({ throwOnError: true })
      return data
    },
    // The roster is a declaration in the server's source, not project state. It
    // changes on deploy, so refetching it per view is pure noise.
    staleTime: 60 * 60 * 1000,
  })
}

/**
 * The one bot whose triggers the message hits, or undefined.
 *
 * Undefined on a tie, deliberately: a message that mentions both a structure
 * and a paper has not chosen an operator, and picking the first match would
 * silently drop half of what was asked. The undifferentiated Copilot handles
 * those, which is what it is for.
 */
export function matchBot(input: string, bots: readonly CopilotBot[]): CopilotBot | undefined {
  const lower = input.toLowerCase()
  const matches = bots.filter((bot) =>
    (bot.triggers ?? []).some((token) => token.length > 0 && lower.includes(token.toLowerCase())),
  )
  return matches.length === 1 ? matches[0] : undefined
}

/** The bots a given bot hands work to, resolved against the roster. */
export function successorsOf(bot: CopilotBot, bots: readonly CopilotBot[]): CopilotBot[] {
  const byId = new Map(bots.map((entry) => [entry.id, entry]))
  return (bot.handoff ?? []).flatMap((id) => {
    const next = byId.get(id)
    return next ? [next] : []
  })
}
