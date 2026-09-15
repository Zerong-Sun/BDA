import { useCallback, useLayoutEffect, useRef } from 'react'
import { useSearchParams } from 'react-router'

/** Keys to set, or to remove when given `null`/`undefined`/`''`. */
export type SearchParamPatch = Record<string, string | null | undefined>

export interface SearchParamPatchOptions {
  /**
   * Replace the history entry instead of pushing one. Use it for selection that
   * changes on every click - a node on a canvas - so Back leaves the page rather
   * than stepping through every node you glanced at.
   */
  replace?: boolean
}

/**
 * Read the query string, and change parts of it without clobbering the rest.
 *
 * `useSearchParams` hands back a setter bound to the render it came from. Two
 * calls from one event - select a run, then clear the node - each start from
 * that same snapshot, so the second silently undoes the first. And the setter's
 * identity changes whenever the URL does, which makes it a poor dependency for
 * memoised canvas callbacks.
 *
 * This keeps the latest params in a ref, merges each patch over them, and
 * returns one stable function. A patch that changes nothing does not navigate,
 * so a pane click with nothing selected does not grow the history.
 */
export function useSearchParamPatch(): [URLSearchParams, (patch: SearchParamPatch, options?: SearchParamPatchOptions) => void] {
  const [search, setSearch] = useSearchParams()
  const latest = useRef({ search, setSearch })

  useLayoutEffect(() => {
    latest.current = { search, setSearch }
  }, [search, setSearch])

  const patch = useCallback((changes: SearchParamPatch, options?: SearchParamPatchOptions) => {
    const next = new URLSearchParams(latest.current.search)
    let changed = false
    for (const [key, value] of Object.entries(changes)) {
      if (value) {
        if (next.get(key) !== value) {
          next.set(key, value)
          changed = true
        }
      } else if (next.has(key)) {
        next.delete(key)
        changed = true
      }
    }
    if (!changed) return
    // Record the result before navigating, so a second patch in the same event
    // starts from this one rather than from the render's snapshot.
    latest.current = { ...latest.current, search: next }
    latest.current.setSearch(next, { replace: options?.replace })
  }, [])

  return [search, patch]
}
