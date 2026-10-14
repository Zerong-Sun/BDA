import { useQuery } from '@tanstack/react-query'
import { ApiError } from '../api/client'
import { authConfigApiV2AuthConfigGet } from '../api/generated/sdk.gen'
import '../api/generatedTransport'
import type { AccountText } from './accountText'

export function useAuthConfig() {
  return useQuery({ queryKey: ['auth-config'], queryFn: async () => (await authConfigApiV2AuthConfigGet<true>()).data, staleTime: 60_000, retry: false })
}

export function accountError(error: unknown, t: AccountText): string {
  if (error instanceof ApiError) {
    const code = (error.payload as { error_code?: string } | undefined)?.error_code
    if (code === 'invalid_account_code') return t.invalidCode
    if (code === 'username_unavailable') return t.unavailableUsername
    if (code === 'invitation_required') return t.inviteRequired
    if (code === 'invitation_username_mismatch') return t.inviteMismatch
    if (code === 'registration_closed') return t.closed
    if (error.status === 401) return t.invalid
    if (error.status === 429) return t.rateLimited
    if (error.status === 412) return t.conflict
    return error.message
  }
  return t.failed
}

export function passwordProblem(password: string, confirmation: string, t: AccountText): string | null {
  if (password !== confirmation) return t.mismatch
  if (new TextEncoder().encode(password).length > 72) return t.passwordTooLong
  if (password.length < 8 || !/\p{L}/u.test(password) || !/\p{N}/u.test(password)) return t.passwordHint
  return null
}

export function safeReturnTo(value: string | null): string {
  return value && /^\/(projects|research|workflow|candidates|results|learning|lab|tools|bots|inbox|extensions|account|autopilot|faq)([/?]|$)/.test(value)
    && !/[\\\r\n]/.test(value) ? value : '/projects'
}

export function portalLoginUrl(value: string | undefined): string | null {
  if (!value) return null
  try {
    const url = new URL(value)
    const local = url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    if ((url.protocol !== 'https:' && !local) || url.username || url.password || url.search || url.hash || url.pathname !== '/') return null
    return `${url.origin}/#/login`
  } catch { return null }
}
