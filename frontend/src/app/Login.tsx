import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { BookOpen } from '@phosphor-icons/react'
import { Alert, AlertDescription } from '@/components/reui/alert'
import { Button } from '@/components/ui/Button'
import { BigoBioLogo } from '@/components/ui/BigoBioLogo'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/label'
import { PasswordField } from '@/components/ui/PasswordField'
import { WorkspacePortals } from '@/features/account/WorkspacePortals'
import { loginApiV2AuthTokenPost, registerApiV2AuthRegisterPost, passwordResetApiV2AuthPasswordResetPost } from '@/lib/api/generated/sdk.gen'
import '@/lib/api/generatedTransport'
import { useI18n } from '@/lib/i18n'
import { useAppStore } from '@/lib/store/appStore'
import { clearAuthenticatedBrowserState } from '@/lib/auth/browserSession'
import { useAccountText } from '@/lib/auth/accountText'
import { accountError, passwordProblem, safeReturnTo, useAuthConfig } from '@/lib/auth/account'

type Mode = 'login' | 'register' | 'reset'

function AuthPage({ mode }: { mode: Mode }) {
  const t = useAccountText()
  const { t: legacy, language } = useI18n()
  const setLanguage = useAppStore(state => state.setLanguage)
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const queryClient = useQueryClient()
  const config = useAuthConfig()
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const invitation = config.data?.registration_mode === 'invite'
  const closed = config.data?.registration_mode === 'closed'
  const title = mode === 'login' ? t.signIn : mode === 'reset' ? t.recover : invitation ? t.invitedRegister : t.register
  const returnTo = safeReturnTo(params.get('returnTo'))

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (loading) return
    setError(null)
    if (mode !== 'login') {
      const problem = passwordProblem(password, confirmation, t)
      if (problem) { setError(problem); return }
    }
    setLoading(true)
    try {
      if (mode === 'reset') {
        await passwordResetApiV2AuthPasswordResetPost<true>({ body: { token: code.trim(), new_password: password } })
        clearAuthenticatedBrowserState(queryClient)
        navigate('/login?notice=password-updated', { replace: true })
      } else {
        const { data } = mode === 'login'
          ? await loginApiV2AuthTokenPost<true>({ body: { username: username.trim(), password } })
          : await registerApiV2AuthRegisterPost<true>({ body: { username: username.trim(), display_name: displayName.trim(), password, ...(code.trim() ? { invitation_token: code.trim() } : {}) } })
        clearAuthenticatedBrowserState(queryClient)
        sessionStorage.setItem('bda_token', data.access_token)
        sessionStorage.setItem('bda_user', JSON.stringify(data.user))
        navigate(mode === 'register' ? '/projects' : returnTo, { replace: true })
      }
    } catch (err) { setError(accountError(err, t)) }
    finally { setLoading(false) }
  }

  return <main className="min-h-screen bg-background px-5 py-10 sm:px-10 lg:py-16" data-tour-id="auth-page">
    <div className="mx-auto max-w-6xl">
      <header className="flex items-center justify-between gap-5">
        <BigoBioLogo className="bigobio-logo--login" />
        <div className="flex items-center gap-4"><Button type="button" variant="ghost" onClick={() => setLanguage(language === 'en' ? 'zh' : 'en')}>{language === 'en' ? '中文' : 'English'}</Button><Link to="/guide" className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary"><BookOpen aria-hidden="true" />{legacy.guide.nav.viewGuide}</Link></div>
      </header>
      <div className="mt-10 grid items-start gap-10 lg:mt-20 lg:grid-cols-[1.1fr_1fr] lg:gap-20">
        <section className="grid gap-6">
          <p className="font-mono text-xs uppercase tracking-widest text-primary">{t.eyebrow}</p>
          <h1 className="whitespace-pre-line text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">{t.hero}</h1>
          <p className="max-w-lg text-base leading-relaxed text-muted-foreground">{t.intro}</p>
          <WorkspacePortals config={config.data} />
          <p className="max-w-lg text-xs leading-relaxed text-muted-foreground">{t.isolation}</p>
        </section>
        <section className="w-full rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8" aria-labelledby="auth-title">
          {config.data ? <p className="mb-3 font-mono text-xs uppercase tracking-widest text-primary">{config.data.deployment_kind === 'public' ? 'Public' : 'Private'}</p> : null}
          <h2 id="auth-title" className="text-2xl font-semibold">{title}</h2>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
            <Link to={`/login?returnTo=${encodeURIComponent(returnTo)}`} aria-current={mode === 'login' ? 'page' : undefined} className={mode === 'login' ? 'font-medium text-primary' : 'text-muted-foreground'}>{t.signIn}</Link>
            {config.data && !closed ? <Link to="/register" aria-current={mode === 'register' ? 'page' : undefined} className={mode === 'register' ? 'font-medium text-primary' : 'text-muted-foreground'}>{invitation ? t.invitedRegister : t.register}</Link> : null}
          </div>
          {config.isError ? <Alert className="mt-5"><AlertDescription>{t.configError} <Button variant="link" type="button" className="underline" onClick={() => void config.refetch()}>{t.retry}</Button></AlertDescription></Alert> : null}
          {params.get('notice') === 'password-updated' && mode === 'login' ? <p role="status" className="mt-5 text-sm text-primary">{t.resetDone}</p> : null}
          {mode === 'register' && closed ? <p role="status" className="mt-6 text-sm text-muted-foreground">{t.closed}</p> : <form onSubmit={handleSubmit} className="mt-6 grid gap-4">
            {error ? <Alert variant="destructive" role="alert"><AlertDescription>{error}</AlertDescription></Alert> : null}
            {mode === 'reset' ? <p className="text-sm leading-relaxed text-muted-foreground">{t.recoveryHelp}</p> : <div className="grid gap-2">
              <Label htmlFor="login-username">{t.username}</Label>
              <Input id="login-username" value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" autoCapitalize="none" spellCheck={false} required maxLength={mode === 'register' ? 64 : 120} />
              {mode === 'register' ? <p className="text-xs text-muted-foreground">{t.usernameHint}</p> : null}
            </div>}
            {mode === 'register' ? <div className="grid gap-2"><Label htmlFor="register-name">{t.displayName}</Label><Input id="register-name" value={displayName} onChange={event => setDisplayName(event.target.value)} autoComplete="nickname" required maxLength={160} /></div> : null}
            {(mode === 'register' && invitation) || mode === 'reset' ? <div className="grid gap-2">
              <Label htmlFor="account-code">{mode === 'reset' ? t.recoveryCode : t.invitation}</Label>
              <Input id="account-code" value={code} onChange={event => setCode(event.target.value)} autoComplete="off" spellCheck={false} required maxLength={256} />
              {invitation && mode === 'register' ? <p className="text-xs text-muted-foreground">{t.codeHelp}</p> : null}
            </div> : null}
            <PasswordField id="login-password" label={mode === 'reset' ? t.newPassword : t.password} value={password} onChange={setPassword} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
            {mode !== 'login' ? <><p className="text-xs text-muted-foreground">{t.passwordHint}</p><PasswordField id="confirm-password" label={t.confirmPassword} value={confirmation} onChange={setConfirmation} /></> : null}
            <Button type="submit" className="mt-2 w-full" disabled={loading || (mode === 'register' && (!config.data || closed))} aria-busy={loading}>{loading ? t.working : title}</Button>
            <Link to={mode === 'login' ? '/reset-password' : '/login'} className="text-center text-sm text-muted-foreground hover:text-primary">{mode === 'login' ? t.forgot : t.back}</Link>
          </form>}
        </section>
      </div>
    </div>
  </main>
}

export function LoginPage() { return <AuthPage key="login" mode="login" /> }
export function RegisterPage() { return <AuthPage key="register" mode="register" /> }
export function ResetPasswordPage() { return <AuthPage key="reset" mode="reset" /> }
