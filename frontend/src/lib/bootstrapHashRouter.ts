/** Move ?project= from page-level search into the hash route (HashRouter compat). */
export function bootstrapHashRouterProjectParam(): void {
  const pageParams = new URLSearchParams(window.location.search)
  const project = pageParams.get('project')
  if (!project) return

  const hash = window.location.hash
  const hashHasProject = hash.includes('project=')
  if (hashHasProject) return

  const hashPath = hash.replace(/^#/, '') || '/experiments'
  const [pathPart, queryPart = ''] = hashPath.split('?')
  const hashParams = new URLSearchParams(queryPart)
  hashParams.set('project', project)
  const nextHash = `#${pathPart}?${hashParams.toString()}`
  const nextUrl = `${window.location.pathname}${nextHash}`
  window.history.replaceState(null, '', nextUrl)
}
