import { resolveBot, type CopilotBot } from './bots/registry'

/**
 * Addressing one member of the room.
 *
 * A room with six operators needs a way to say who a message is for, and the
 * roster rail cannot be it: the rail is where you *go to* someone's desk, which
 * is a different act from turning to them mid-conversation.
 *
 * Three rules, and each exists because its absence is a silent failure:
 *
 * * **The mention narrows exactly one turn.** It becomes that request's `bot`
 *   hint, which the server intersects with the project's enabled capabilities -
 *   so addressing someone can only ever take capabilities away, never add them.
 *   A mention that pinned the conversation would make "ask Runner one thing"
 *   quietly re-route everything after it.
 * * **A handle that resolves to nobody is refused, not ignored.** Falling back
 *   to auto-match would send the message to somebody else while the person
 *   believes they addressed Runner, and nothing on screen would say so.
 * * **A retired id resolves to its successor.** The roster merged twelve
 *   operators into six; a person who learned `@structuralist` last week should
 *   reach Planner rather than a "no such member" they cannot act on.
 */

export interface Mention {
  /** What was typed after the `@`, as typed. */
  handle: string
  /** The operator it resolves to, absent when the handle names nobody. */
  bot?: CopilotBot
  /** The message with the handle removed: what the work is, without the address. */
  body: string
}

/** Every way one operator can be named, longest first so a prefix match is greedy. */
function handlesOf(bots: readonly CopilotBot[]): { handle: string; bot: CopilotBot }[] {
  return bots
    .flatMap((bot) => [bot.id, bot.title, bot.title_zh, ...(bot.absorbs ?? [])]
      .filter((name): name is string => Boolean(name))
      .map((name) => ({ handle: name.toLowerCase(), bot })))
    .sort((a, b) => b.handle.length - a.handle.length)
}

/**
 * The operator a message is addressed to, or null when it addresses nobody.
 *
 * Only a leading `@` counts. A handle in the middle of a sentence is usually a
 * reference to an operator ("ask planner whether…") rather than an address, and
 * treating those alike would re-route messages on a word.
 */
export function parseMention(text: string, bots: readonly CopilotBot[]): Mention | null {
  const match = /^\s*@(\S+)/.exec(text)
  if (!match) return null
  const typed = match[1].replace(/[:：,，.。]+$/, '')
  const rest = text.slice(match.index + match[0].length).trim()
  const lower = typed.toLowerCase()
  const candidates = handlesOf(bots)

  const exact = candidates.find((entry) => entry.handle === lower)
  if (exact) return { handle: typed, bot: resolveBot(exact.bot.id, bots) ?? exact.bot, body: rest }

  // Chinese names carry no word boundary, so `@方案设计帮我看一下` arrives as one
  // token. Longest prefix wins, and the remainder rejoins the message rather
  // than being dropped - the part after the name is what the work is.
  const prefixed = candidates.find((entry) => lower.startsWith(entry.handle))
  if (prefixed) {
    const remainder = typed.slice(prefixed.handle.length)
    return {
      handle: typed.slice(0, prefixed.handle.length),
      bot: resolveBot(prefixed.bot.id, bots) ?? prefixed.bot,
      body: [remainder, rest].filter(Boolean).join(' ').trim(),
    }
  }
  return { handle: typed, body: rest }
}

/** The recipe this operator owns, when it takes guided tasks at all. */
export function ownedService(bot: CopilotBot | undefined): string | undefined {
  return bot?.task_services?.[0]
}
