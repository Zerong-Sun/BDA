import type { QueryClient } from '@tanstack/react-query'
import { useAppStore } from '../store/appStore'

const AUTHENTICATED_SESSION_KEYS = [
  'bda_token',
  'bda_user',
  'bda_copilot_last_mode',
]

/** Remove every user- or project-scoped browser value while preserving UI preferences. */
export function clearAuthenticatedBrowserState(queryClient?: QueryClient): void {
  for (const key of AUTHENTICATED_SESSION_KEYS) sessionStorage.removeItem(key)
  queryClient?.clear()
  useAppStore.getState().resetAuthenticatedState()
}
