import type { AuthConfigResponse } from '@/lib/api/generated/types.gen'
import { portalUrl } from '@/lib/auth/account'
import { useAccountText } from '@/lib/auth/accountText'
import { Button } from '@/components/ui/Button'

export function PrivateAccessLinks({ config }: { config?: AuthConfigResponse }) {
  const t = useAccountText()
  const local = config?.deployment_kind === 'private'
  const login = local ? '#/login' : portalUrl(config?.private_portal_url, 'login')
  const register = local ? '#/register' : portalUrl(config?.private_portal_url, 'register')
  return <div className="space-y-3">
    <div className="flex flex-wrap gap-3">
      {register ? <Button render={<a href={register} />}>{t.privateRegister}</Button> : null}
      {login ? <Button variant="outline" render={<a href={login} />}>{t.privateLogin}</Button> : null}
    </div>
    <p className="text-xs leading-6 text-muted-foreground">{login ? t.privateAccountHelp : config ? t.privateUnavailable : t.working}</p>
  </div>
}
