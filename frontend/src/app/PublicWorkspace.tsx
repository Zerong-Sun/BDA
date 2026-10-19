import { useEffect } from 'react'
import { Navigate, useSearchParams } from 'react-router'
import { Button } from '../components/ui/Button'
import { portalUrl, useAuthConfig } from '../lib/auth/account'
import { useI18n } from '../lib/i18n'

/** Compatibility entry: Public opens the full workbench, never a separate showcase. */
export function PublicWorkspacePage() {
  const { data, isPending, refetch } = useAuthConfig()
  const { language } = useI18n()
  const [params] = useSearchParams()
  const publicUrl = data?.deployment_kind === 'private' ? portalUrl(data.public_portal_url, 'public') : null
  useEffect(() => {
    if (publicUrl && new URL(publicUrl).origin !== window.location.origin) window.location.replace(publicUrl)
  }, [publicUrl])
  if (data?.deployment_kind === 'public') {
    const destination = params.get('view') === 'tools' ? '/tools' : '/projects'
    const next = new URLSearchParams(params)
    next.delete('view')
    return <Navigate to={`${destination}${next.size ? `?${next}` : ''}`} replace />
  }
  if (isPending) return <p role="status" className="p-8">{language === 'zh' ? '正在进入工作区…' : 'Opening workspace…'}</p>
  return <main className="space-y-4 p-8"><p>{language === 'zh' ? '进入 Public 工作区，无需账号。' : 'Enter the Public workspace without an account.'}</p>{publicUrl ? <a className="text-primary underline" href={publicUrl}>{language === 'zh' ? '进入 Public' : 'Enter Public'}</a> : <Button type="button" onClick={() => void refetch()}>{language === 'zh' ? '重新加载工作区入口' : 'Reload workspace links'}</Button>}</main>
}
