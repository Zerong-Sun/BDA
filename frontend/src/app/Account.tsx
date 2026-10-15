import { useEffect, useState } from 'react'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { Alert, AlertDescription } from '@/components/reui/alert'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/label'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { PasswordField } from '@/components/ui/PasswordField'
import { WorkspacePortals } from '@/features/account/WorkspacePortals'
import {
  accountApiV2AuthAccountGet, passwordChangeApiV2AuthPasswordPost,
  listAccountGrantsApiV2AuthGrantsGet, issueAccountGrantApiV2AuthGrantsPost,
  revokeAccountGrantApiV2AuthGrantsGrantIdRevokePost, listOrganizationsApiV2OrganizationsGet,
} from '@/lib/api/generated/sdk.gen'
import type { AccountGrantIssued, AccountGrantResponse } from '@/lib/api/generated/types.gen'
import '@/lib/api/generatedTransport'
import { accountError, passwordProblem, useAuthConfig } from '@/lib/auth/account'
import { useAccountText } from '@/lib/auth/accountText'
import { clearAuthenticatedBrowserState } from '@/lib/auth/browserSession'
import { useI18n } from '@/lib/i18n'
import { isPublicVisitor } from '@/lib/auth/publicWorkspace'
import { PrivateAccessLinks } from '@/features/account/PrivateAccessLinks'


function AccountGrants() {
  const t = useAccountText()
  const { language } = useI18n()
  const queryClient = useQueryClient()
  const organizations = useQuery({ queryKey: ['account-organizations'], queryFn: async () => (await listOrganizationsApiV2OrganizationsGet<true>()).data })
  const grants = useInfiniteQuery({
    queryKey: ['account-grants'], initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => (await listAccountGrantsApiV2AuthGrantsGet<true>({ query: { limit: 30, ...(pageParam ? { cursor: pageParam } : {}) } })).data,
    getNextPageParam: page => page.next_cursor ?? undefined,
  })
  const [purpose, setPurpose] = useState<'invitation' | 'password_reset'>('invitation')
  const [username, setUsername] = useState('')
  const [organizationId, setOrganizationId] = useState('')
  const [memberRole, setMemberRole] = useState<'viewer' | 'researcher'>('viewer')
  const [hours, setHours] = useState('24')
  const [issued, setIssued] = useState<AccountGrantIssued | null>(null)
  const [copied, setCopied] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const config = useAuthConfig()
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 30_000); return () => window.clearInterval(timer) }, [])

  const issue = async (event: React.FormEvent) => {
    event.preventDefault()
    if (pending || issued) return
    setPending(true); setError(null); setCopied(false)
    try {
      const { data } = await issueAccountGrantApiV2AuthGrantsPost<true>({ body: {
        purpose, username: username.trim(), ...(purpose === 'invitation' ? { organization_id: organizationId, member_role: memberRole } : {}),
        expires_in_hours: purpose === 'password_reset' ? 1 : Number(hours),
      } })
      setIssued(data)
      await queryClient.invalidateQueries({ queryKey: ['account-grants'] })
    } catch (err) { setError(accountError(err, t)) }
    finally { setPending(false) }
  }
  const revoke = async (grant: AccountGrantResponse) => {
    setPending(true); setError(null)
    try {
      await revokeAccountGrantApiV2AuthGrantsGrantIdRevokePost<true>({ path: { grant_id: grant.id }, headers: { 'If-Match': `W/"${grant.version}"` } })
      if (issued?.grant.id === grant.id) setIssued(null)
      await queryClient.invalidateQueries({ queryKey: ['account-grants'] })
    } catch (err) { setError(accountError(err, t)); await grants.refetch() }
    finally { setPending(false) }
  }
  const status = (grant: AccountGrantResponse) => grant.revoked_at ? 'revoked' : grant.used_at ? 'used' : Date.parse(grant.expires_at) <= now ? 'expired' : 'active'
  const date = (value: string) => new Intl.DateTimeFormat(language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))

  return <section className="rounded-xl border bg-card p-5 sm:p-7" aria-labelledby="account-grants-heading">
    <h2 id="account-grants-heading" className="text-xl font-semibold">{t.grantsTitle}</h2>
    <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">{t.grantsBody}</p>
    {(organizations.isError || grants.isError) ? <Alert className="mt-4" variant="destructive"><AlertDescription>{t.adminLoadError} <Button variant="link" className="underline" type="button" onClick={() => { void organizations.refetch(); void grants.refetch() }}>{t.retry}</Button></AlertDescription></Alert> : null}
    {error ? <Alert variant="destructive" className="mt-4" role="alert"><AlertDescription>{error}</AlertDescription></Alert> : null}
    <form onSubmit={issue} className="mt-5 grid max-w-3xl gap-4 sm:grid-cols-2">
      <div className="grid gap-2"><Label htmlFor="grant-purpose">{t.purpose}</Label><Select value={purpose} onValueChange={value => { if (value) setPurpose(value) }}><SelectTrigger id="grant-purpose" className="w-full"><SelectValue>{purpose === 'invitation' ? t.invitePurpose : t.resetPurpose}</SelectValue></SelectTrigger><SelectContent><SelectItem value="invitation">{t.invitePurpose}</SelectItem><SelectItem value="password_reset">{t.resetPurpose}</SelectItem></SelectContent></Select></div>
      <div className="grid gap-2"><Label htmlFor="grant-username">{t.username}</Label><Input id="grant-username" value={username} onChange={e => setUsername(e.target.value)} autoComplete="off" required maxLength={120} /></div>
      {purpose === 'invitation' ? <>
        <div className="grid gap-2"><Label htmlFor="grant-organization">{t.organization}</Label><Select value={organizationId || null} onValueChange={value => setOrganizationId(value ?? '')} required><SelectTrigger id="grant-organization" className="w-full"><SelectValue placeholder={t.chooseOrganization}>{organizations.data?.find(org => org.id === organizationId)?.name}</SelectValue></SelectTrigger><SelectContent>{organizations.data?.map(org => <SelectItem key={org.id} value={org.id}>{org.name}</SelectItem>)}</SelectContent></Select></div>
        <div className="grid gap-2"><Label htmlFor="grant-role">{t.memberRole}</Label><Select value={memberRole} onValueChange={value => { if (value) setMemberRole(value) }}><SelectTrigger id="grant-role" className="w-full"><SelectValue>{memberRole === 'viewer' ? t.viewer : t.researcher}</SelectValue></SelectTrigger><SelectContent><SelectItem value="viewer">{t.viewer}</SelectItem><SelectItem value="researcher">{t.researcher}</SelectItem></SelectContent></Select></div>
        <div className="grid gap-2"><Label htmlFor="grant-hours">{t.hours}</Label><Input id="grant-hours" type="number" min={1} max={168} step={1} required value={hours} onChange={e => setHours(e.target.value)} /></div>
      </> : <p className="text-sm text-muted-foreground sm:col-span-2">{t.recoveryHelp}</p>}
      <div className="flex items-end"><Button type="submit" disabled={pending || Boolean(issued) || (purpose === 'invitation' && (!config.data || config.data.registration_mode === 'closed' || !organizations.data || !organizationId))}>{pending ? t.working : t.issue}</Button></div>
    </form>
    {purpose === 'invitation' && config.data?.registration_mode === 'closed' ? <p role="status" className="mt-3 text-sm text-muted-foreground">{t.closed}</p> : null}
    {issued ? <div className="mt-6 max-w-3xl rounded-lg border border-primary/40 bg-primary/5 p-4" role="status">
      <h3 className="font-semibold">{t.issued}</h3><p className="mt-2 text-sm">{issued.grant.username} · {t.expires}: {date(issued.grant.expires_at)}</p>
      <p className="my-3 text-sm text-muted-foreground">{t.issuedHelp}</p>
      <Input readOnly aria-label={issued.grant.purpose === 'invitation' ? t.invitation : t.recoveryCode} value={issued.token} className="font-mono" />
      <div className="mt-3 flex gap-2"><Button type="button" variant="outline" onClick={() => { void (async () => { try { await navigator.clipboard.writeText(issued.token); setCopied(true) } catch { setError(t.copyFailed) } })() }}>{copied ? t.copied : t.copy}</Button><Button type="button" variant="ghost" onClick={() => setIssued(null)}>{t.dismiss}</Button></div>
    </div> : null}
    <h3 className="mb-3 mt-8 font-medium">{t.codeHistory}</h3>
    {grants.data?.pages[0]?.items.length === 0 ? <p className="text-sm text-muted-foreground">{t.noCodes}</p> : null}
    <div className="grid gap-3">{grants.data?.pages.flatMap(page => page.items).map(grant => <article key={grant.id} className="flex flex-wrap items-center justify-between gap-4 rounded-lg border p-4">
      <div><p className="font-medium">{grant.username} <span className="ml-2 text-xs font-normal text-muted-foreground">{grant.purpose === 'invitation' ? t.invitePurpose : t.resetPurpose}</span></p><p className="mt-1 text-xs text-muted-foreground">{t.expires}: {date(grant.expires_at)} · {t.status}: {t[status(grant)]}</p></div>
      {status(grant) === 'active' ? <Button type="button" variant="outline" disabled={pending} onClick={() => void revoke(grant)}>{t.revoke}</Button> : null}
    </article>)}</div>
    {grants.hasNextPage ? <Button type="button" className="mt-4" variant="outline" disabled={grants.isFetchingNextPage} onClick={() => void grants.fetchNextPage()}>{t.more}</Button> : null}
  </section>
}

export function AccountPage() {
  return isPublicVisitor() ? <PublicAccountAccess /> : <SignedInAccount />
}

function PublicAccountAccess() {
  const { language } = useI18n()
  const config = useAuthConfig()
  return <section className="mx-auto max-w-2xl space-y-5 py-8">
    <h1 className="text-2xl font-semibold">{language === 'zh' ? '进入 Private 开展研究' : 'Work on your research in Private'}</h1>
    <p className="text-muted-foreground">{language === 'zh' ? 'Public 无需账号。注册或登录 Private 后，可创建项目、保存分析和运行 Bot 任务。' : 'Public needs no account. Register or sign in to Private to create projects, save analyses and run Bot tasks.'}</p>
    <PrivateAccessLinks config={config.data} />
  </section>
}

function SignedInAccount() {
  const t = useAccountText()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const config = useAuthConfig()
  const account = useQuery({ queryKey: ['my-account'], queryFn: async () => (await accountApiV2AuthAccountGet<true>()).data })
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const change = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!account.data || pending) return
    const problem = passwordProblem(password, confirmation, t)
    if (problem) { setError(problem); return }
    setPending(true); setError(null)
    try {
      await passwordChangeApiV2AuthPasswordPost<true>({ body: { current_password: current, new_password: password }, headers: { 'If-Match': `W/"${account.data.version}"` } })
      clearAuthenticatedBrowserState(queryClient)
      navigate('/login?notice=password-updated', { replace: true })
    } catch (err) { setError(accountError(err, t)) }
    finally { setPending(false) }
  }
  return <div className="mx-auto grid max-w-5xl gap-7 px-4 py-8 sm:px-6">
    <header><h1 className="text-3xl font-semibold">{t.account}</h1><p className="mt-2 text-muted-foreground">{t.accountBody}</p></header>
    <WorkspacePortals config={config.data} />
    {config.isError ? <Alert><AlertDescription>{t.configError} <Button type="button" variant="link" onClick={() => void config.refetch()}>{t.retry}</Button></AlertDescription></Alert> : null}
    <p className="text-sm text-muted-foreground">{t.isolation}</p>
    {account.isPending ? <p role="status">{t.accountLoading}</p> : null}
    {account.isError ? <Alert variant="destructive"><AlertDescription>{t.failed} <Button variant="link" type="button" className="underline" onClick={() => void account.refetch()}>{t.retry}</Button></AlertDescription></Alert> : null}
    {account.data ? <section className="grid gap-7 rounded-xl border bg-card p-5 sm:grid-cols-2 sm:p-7">
      <div><h2 className="text-xl font-semibold">{account.data.display_name}</h2><dl className="mt-5 grid grid-cols-[auto_1fr] gap-x-5 gap-y-3 text-sm"><dt className="text-muted-foreground">{t.username}</dt><dd>{account.data.username}</dd><dt className="text-muted-foreground">{t.role}</dt><dd>{account.data.role}</dd><dt className="text-muted-foreground">{t.realm}</dt><dd>{config.data?.deployment_kind === 'public' ? 'Public' : config.data?.deployment_kind === 'private' ? 'Private' : '—'}</dd></dl></div>
      <div><h2 className="text-xl font-semibold">{t.passwordTitle}</h2><p className="mt-2 text-sm leading-relaxed text-muted-foreground">{account.data.has_password ? t.passwordChangeHelp : t.externalAccount}</p>
        {account.data.has_password ? <form onSubmit={change} className="mt-5 grid gap-4">
          {error ? <Alert variant="destructive" role="alert"><AlertDescription>{error} <Button variant="link" type="button" className="underline" onClick={() => void account.refetch()}>{t.retry}</Button></AlertDescription></Alert> : null}
          <PasswordField id="account-current-password" label={t.currentPassword} value={current} onChange={setCurrent} autoComplete="current-password" />
          <PasswordField id="account-new-password" label={t.newPassword} value={password} onChange={setPassword} />
          <PasswordField id="account-confirm-password" label={t.confirmPassword} value={confirmation} onChange={setConfirmation} />
          <p className="text-xs text-muted-foreground">{t.passwordHint}</p><Button type="submit" disabled={pending}>{pending ? t.working : t.changePassword}</Button>
        </form> : null}
      </div>
    </section> : null}
    {account.data?.role === 'admin' ? <AccountGrants /> : null}
  </div>
}
