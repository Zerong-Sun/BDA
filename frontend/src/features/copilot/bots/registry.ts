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
 *
 * One case is not that kind of tie: a token that is a strict substring of
 * another token the same message matched. "literature review" hits
 * `librarian`'s phrase and `auditor`'s bare "review" at once - one phrase
 * matched twice, not two operators named - and calling it ambiguous would make
 * both unroutable by the word that names them. So a match is discarded when
 * some other match contains it, and whatever survives decides.
 *
 * Containment, not length. Length would rank "residue" over "paper", which are
 * equally specific and merely different sizes, and that tie has to survive.
 *
 * This replaces the hand-written skill registry's fixed preference for anything
 * over `project-read` and `research-read`: stated as containment it needs no
 * list, and so no list to keep in step with the roster.
 */
export function matchBot(input: string, bots: readonly CopilotBot[]): CopilotBot | undefined {
  const lower = input.toLowerCase()
  const hits = bots.flatMap((bot) =>
    (bot.triggers ?? [])
      .map((token) => token.toLowerCase())
      .filter((token) => token.length > 0 && lower.includes(token))
      .map((token) => ({ bot, token })),
  )
  const surviving = hits.filter(
    (hit) => !hits.some((other) => other.token.length > hit.token.length && other.token.includes(hit.token)),
  )
  const named = new Set(surviving.map((hit) => hit.bot.id))
  return named.size === 1 ? surviving[0].bot : undefined
}

/** The bots a given bot hands work to, resolved against the roster. */
export function successorsOf(bot: CopilotBot, bots: readonly CopilotBot[]): CopilotBot[] {
  const byId = new Map(bots.map((entry) => [entry.id, entry]))
  return (bot.handoff ?? []).flatMap((id) => {
    const next = byId.get(id)
    return next ? [next] : []
  })
}

/** Operators grouped by what they are for, in the order a picker should show them.
 *
 * The labels live in the i18n bundles, not here. A `STANCE_LABELS` map sat in
 * this file for one commit, in English only, read by nothing - the same
 * declared-and-never-read shape as the `systemPrompt` field on the capability
 * list this module replaced.
 */
export const STANCE_ORDER = ['direct', 'produce', 'review'] as const

export type Stance = (typeof STANCE_ORDER)[number]

/**
 * The roster split by stance, so the picker groups by responsibility rather
 * than by phase number.
 *
 * Grouping by phase put the director at the top and the reviewer at the bottom
 * of one flat list, which reads as "step -1" and "step 9" - positions in a
 * sequence that neither of them occupies. A director is not the step before
 * briefing and a reviewer is not the step after archiving; they sit beside the
 * chain, and the picker should say so.
 */
export function byStance(bots: readonly CopilotBot[]): { stance: Stance; bots: CopilotBot[] }[] {
  return STANCE_ORDER.map((stance) => ({
    stance,
    bots: bots.filter((bot) => bot.stance === stance),
  })).filter((group) => group.bots.length > 0)
}

/**
 * Who checks this operator, resolved against the roster.
 *
 * Read from `reviewed_by`, which the server derives from the reviewers' own
 * declarations - a producer does not choose who reviews it, so this is not
 * something the client could assemble from the producer's own row.
 */
export function reviewersOf(bot: CopilotBot, bots: readonly CopilotBot[]): CopilotBot[] {
  const byId = new Map(bots.map((entry) => [entry.id, entry]))
  return (bot.reviewed_by ?? []).flatMap((id) => {
    const next = byId.get(id)
    return next ? [next] : []
  })
}
