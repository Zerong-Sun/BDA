import { useAuthConfig, portalUrl } from '../../lib/auth/account'
import { isPublicVisitor } from '../../lib/auth/publicWorkspace'
import { useI18n } from '../../lib/i18n'

export function PublicWorkspaceNotice() {
  const { language } = useI18n()
  const { data } = useAuthConfig()
  if (!isPublicVisitor()) return null
  const register = portalUrl(data?.private_portal_url, 'register')
  const login = portalUrl(data?.private_portal_url, 'login')
  return <aside className="public-workspace-notice" aria-label="Public workspace">
    <span className="sm:hidden">{language === 'zh' ? 'Public · 免登录浏览' : 'Public · No account needed'}</span>
    <span className="hidden sm:inline">{language === 'zh' ? 'Public 工作区 · 免账号浏览全部公开研究页面' : 'Public workspace · Explore published research without an account'}</span>
    <span className="public-workspace-links"><span className="hidden text-muted-foreground lg:inline">{language === 'zh' ? '开展自己的研究，进入 Private' : 'Work on your own research in Private'}</span>{register ? <a href={register}>{language === 'zh' ? '注册' : 'Register'}</a> : null}{login ? <a href={login}>{language === 'zh' ? '登录' : 'Sign in'}</a> : null}</span>
  </aside>
}
