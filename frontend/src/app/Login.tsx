import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { BookOpen } from '@phosphor-icons/react'
import { Alert, AlertDescription } from '@/components/reui/alert'
import { AppFrame } from '@/components/ui/AppFrame'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/label'
import { ApiError } from '../lib/api/client'
import { loginApiV2AuthTokenPost } from '../lib/api/generated/sdk.gen'
import '../lib/api/generatedTransport'
import { useI18n } from '../lib/i18n'

export function LoginPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const loginErrorMessage = (err: unknown): string => {
    if (err instanceof ApiError) {
      if (err.status === 401) return t.login.errorInvalidCredentials
      if (err.status === 429) return t.login.errorTooManyAttempts
      return err.message
    }
    return err instanceof Error ? err.message : t.login.errorFailed
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const { data } = await loginApiV2AuthTokenPost<true>({ body: { username, password }, throwOnError: true })
      sessionStorage.setItem('bda_token', data.access_token)
      sessionStorage.setItem('bda_user', JSON.stringify(data.user))
      navigate('/projects')
    } catch (err) {
      setError(loginErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-[80vh] items-center justify-center px-4">
      <div className="grid w-full max-w-4xl items-center gap-8 md:grid-cols-2">
        <section className="hidden flex-col gap-4 md:flex">
          <p className="text-xs uppercase tracking-wide text-accent">{t.login.brandEyebrow}</p>
          <h1 className="text-3xl font-semibold leading-tight text-text-primary">{t.login.heroTitle}</h1>
          <p className="text-sm text-text-secondary">{t.login.heroBody}</p>
          <ul className="grid gap-2 text-sm text-text-secondary">
            {[t.login.heroBullet1, t.login.heroBullet2, t.login.heroBullet3].map((item) => (
              <li key={item} className="flex items-start gap-2">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                {item}
              </li>
            ))}
          </ul>
          <Button className="mt-4 w-fit" variant="outline" render={<Link to="/guide" />}>
            <BookOpen className="h-4 w-4" aria-hidden="true" />
            {t.guide.nav.viewGuide}
          </Button>
        </section>
        <AppFrame
          heading={<h1>{t.login.formTitle}</h1>}
          description={t.login.formSubtitle}
          className="w-full max-w-sm justify-self-center md:justify-self-start"
          panelClassName="p-0"
        >
          <form onSubmit={handleSubmit} className="grid gap-4 border-t border-border p-5">
            {error ? (
              <Alert variant="destructive" aria-live="assertive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            <div className="grid gap-2">
              <Label htmlFor="login-username">{t.login.usernameLabel}</Label>
              <Input
                id="login-username"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="login-password">{t.login.passwordLabel}</Label>
              <Input
                id="login-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              className="w-full"
              aria-busy={loading}
            >
              {loading ? t.login.signingIn : t.login.signIn}
            </Button>
            <p className="text-center md:hidden">
              <Link to="/guide" className="text-sm text-accent hover:underline">
                {t.guide.nav.viewGuide}
              </Link>
            </p>
          </form>
        </AppFrame>
      </div>
    </div>
  )
}
