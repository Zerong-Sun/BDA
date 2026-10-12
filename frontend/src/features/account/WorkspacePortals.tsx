import { ArrowUpRightIcon, LockKeyIcon, GlobeHemisphereWestIcon } from '@phosphor-icons/react'
import { useAccountText } from '@/lib/auth/accountText'
import { portalLoginUrl } from '@/lib/auth/account'
import type { AuthConfigResponse } from '@/lib/api/generated/types.gen'

export function WorkspacePortals({ config }: { config?: AuthConfigResponse }) {
  const t = useAccountText()
  return <nav aria-label={t.portalLabel} className="grid gap-3 sm:grid-cols-2">
    {(['public', 'private'] as const).map(kind => {
      const current = config?.deployment_kind === kind
      const title = kind === 'public' ? t.publicTitle : t.privateTitle
      const url = portalLoginUrl(kind === 'public' ? config?.public_portal_url : config?.private_portal_url)
      const content = <><span className="flex items-center justify-between gap-3 font-medium">{kind === 'public' ? <GlobeHemisphereWestIcon aria-hidden="true" /> : <LockKeyIcon aria-hidden="true" />}{title}{!current && url ? <ArrowUpRightIcon aria-hidden="true" /> : null}</span><span className="mt-2 block text-xs leading-relaxed text-muted-foreground">{kind === 'public' ? t.publicBody : t.privateBody}</span></>
      const style = `rounded-xl border p-4 text-sm ${current ? 'border-primary bg-primary/5' : 'border-border bg-background'}`
      return current || !url ? <div key={kind} aria-current={current ? 'location' : undefined} className={style}>{content}</div> : <a key={kind} className={`${style} hover:border-primary`} href={url} rel="noreferrer">{content}</a>
    })}
  </nav>
}
