/**
 * The app's routes, once.
 *
 * This list lived inside `Topbar.tsx`, which was fine while the top bar was the
 * only thing that needed it. A command palette needs the same list, and a
 * second copy of "which routes exist and what they are called" is the kind of
 * duplication that goes wrong quietly: a route renamed in one place keeps its
 * old name in the other, and nothing fails.
 *
 * `key` indexes `t.nav`, except for the two the navigation deliberately words
 * differently from their page titles - the inbox is "what waits on me" rather
 * than "inbox", and the roster is "the research team" rather than "bots". Those
 * two overrides live here with the list rather than at each call site.
 */

export interface AppRoute {
  to: string
  key: 'projects' | 'inbox' | 'bots' | 'research' | 'workflow' | 'candidates' | 'lab' | 'results' | 'timeline' | 'faq'
}

/**
 * The routes `t.nav` can translate.
 *
 * `inbox` and `bots` are deliberately absent from it: navigation words them
 * differently from their page titles, so they have no `t.nav` entry at all.
 * Encoding that here means a caller cannot pass a translator that would be
 * asked for a key it does not have.
 */
export type NavTranslationKey = Exclude<AppRoute['key'], 'inbox' | 'bots'>

/** Every route reachable from navigation, in the order a person meets them. */
export const APP_ROUTES: readonly AppRoute[] = [
  { to: '/projects', key: 'projects' },
  { to: '/inbox', key: 'inbox' },
  { to: '/bots', key: 'bots' },
  { to: '/research', key: 'research' },
  { to: '/workflow', key: 'workflow' },
  { to: '/candidates', key: 'candidates' },
  { to: '/lab', key: 'lab' },
  { to: '/results', key: 'results' },
  { to: '/timeline', key: 'timeline' },
  { to: '/faq', key: 'faq' },
]

/**
 * Ordered by who acts: the project, what waits on you, the team that works on
 * it, and the research record. The stage workbenches follow behind one menu on
 * desktop; on small screens every route stays a link for reachability.
 */
export const PRIMARY_ROUTES: readonly string[] = ['/projects', '/inbox', '/bots', '/research']

/** Routes that sit behind the Workbenches menu rather than in the primary bar. */
export function workbenchRoutes(): AppRoute[] {
  return APP_ROUTES.filter((route) => !PRIMARY_ROUTES.includes(route.to) && route.to !== '/faq')
}

/**
 * The label a route carries in navigation.
 *
 * `translate` is passed in rather than imported so this module stays free of
 * React and can be used by a plain function, a test, or the palette's search
 * index without pulling the i18n provider along.
 */
export function routeLabel(
  key: AppRoute['key'],
  zh: boolean,
  translate: (key: NavTranslationKey) => string,
): string {
  // Both overrides return before the fallback, which is what narrows `key` to
  // the subset `t.nav` actually carries.
  if (key === 'inbox') return zh ? '待我决定' : 'Decisions'
  if (key === 'bots') return zh ? '研究团队' : 'Research team'
  return translate(key)
}
