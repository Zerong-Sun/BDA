import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Navigate, Outlet, useLocation } from 'react-router'
import { Button } from '../../components/ui/Button'
import { useAuthConfig } from '../../lib/auth/account'
import { meApiV2AuthMeGet } from '../../lib/api/generated/sdk.gen'
import { useI18n } from '../../lib/i18n'
import { ApiError, currentAuthGeneration, refreshAccessToken } from '../../lib/api/client'

/** Public uses the same workspace routes and components, without a login token. */
export function WorkspaceAccessGate() {
  const location = useLocation()
  const { language } = useI18n()
  const zh = language === 'zh'
  const token = sessionStorage.getItem('bda_token')
  const config = useAuthConfig()
  const publicAccess = config.data?.deployment_kind === 'public' && config.data.public_workspace_enabled === true
  const [generation] = useState(currentAuthGeneration)
  const privateAccess = config.data?.deployment_kind === 'private'
  const canRestore = !token && privateAccess && generation === currentAuthGeneration()
  // A new tab has no sessionStorage token, but may still have this realm's
  // HttpOnly refresh cookie. Resolve that session before redirecting a deep link.
  // The shared refresh helper handles single flight, account identity, and late
  // responses after logout; this mounted gate never starts a new auth generation.
  const restored = useQuery({
    queryKey: ['private-workspace-session', config.data?.realm, generation],
    queryFn: () => refreshAccessToken(),
    enabled: canRestore,
    retry: false,
    staleTime: Infinity,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
  const restoreUnavailable = canRestore && restored.isError
    && !(restored.error instanceof ApiError && [401, 403].includes(restored.error.status))
  const identity = useQuery({
    queryKey: ['public-workspace-identity'],
    queryFn: async ({ signal }) => {
      const user = (await meApiV2AuthMeGet<true>({ signal })).data
      if (user.role !== 'viewer') throw new Error('Public requires read-only access')
      // Install display permissions before mounting workspace components. Never
      // overwrite an account that signed in while this request was in flight.
      if (!signal.aborted && !sessionStorage.getItem('bda_token')) sessionStorage.setItem('bda_user', JSON.stringify({ ...user, public_visitor: true }))
      return user
    },
    enabled: !token && publicAccess, retry: false, staleTime: 60_000,
  })
  if (token) return <Outlet />
  if (config.isError || (publicAccess && identity.isError) || restoreUnavailable) return <main className="space-y-4 p-8"><p role="alert">{zh ? '工作区暂时无法加载，请重试。' : 'The workspace could not be loaded. Please retry.'}</p><Button type="button" onClick={() => { void config.refetch(); if (publicAccess) void identity.refetch(); if (restoreUnavailable) void restored.refetch() }}>{zh ? '重试' : 'Retry'}</Button></main>
  if (config.isPending || (publicAccess && !identity.data) || (canRestore && restored.isPending)) return <p role="status" className="p-8">{zh ? '正在进入工作区…' : 'Opening workspace…'}</p>
  if (publicAccess) return <Outlet />
  return <Navigate to={`/login?returnTo=${encodeURIComponent(location.pathname + location.search)}`} replace />
}
