import { HashRouter, Navigate, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useMemo, useRef } from 'react'
import { useI18n } from './lib/i18n'
import { Topbar } from './components/ui/Topbar'
import { Button } from './components/ui/Button'
import { PipelineRail } from './components/ui/PipelineRail'
import { Toast } from './components/ui/Toast'
import { CopilotDrawer } from './components/ui/CopilotDrawer'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { AppSettingsDrawer } from './components/ui/AppSettingsDrawer'
import { ActivityDrawer } from './features/operations/ActivityDrawer'
import { ProjectRequired } from './features/projects/ProjectRequired'
import { ApiError, setUnauthorizedHandler } from './lib/api/client'
import { useProjectContext } from './lib/hooks/useProjectContext'
import { useProjectEvents } from './lib/hooks/useProjectEvents'
import { useAppStore } from './lib/store/appStore'
import { applyTheme, resolveTheme, watchSystemTheme } from './lib/theme/initTheme'
import { isDemoProject, TourOverlay } from './features/tour'
import { clearAuthenticatedBrowserState } from './lib/auth/browserSession'
import { WorkspaceAccessGate } from './features/account/WorkspaceAccessGate'
import { PublicWorkspaceNotice } from './features/account/PublicWorkspaceNotice'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Retry transient failures up to 3 times, but never retry client errors
      // (4xx) such as 401/404 where retrying cannot help.
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
          return false
        }
        return failureCount < 3
      },
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30_000),
    },
    mutations: {
      // Mutations may create projects, upload artifacts, or submit compute.
      // Retrying them without an idempotency key can duplicate side effects.
      retry: false,
    },
  },
})

const ExperimentsPage = lazy(() => import('./app/Experiments').then((module) => ({ default: module.ExperimentsPage })))
const WorkflowPage = lazy(() => import('./app/Workflow').then((module) => ({ default: module.WorkflowPage })))
const CandidatesPage = lazy(() => import('./app/Candidates').then((module) => ({ default: module.CandidatesPage })))
const LearningPage = lazy(() => import('./app/Learning').then((module) => ({ default: module.LearningPage })))
const LabPage = lazy(() => import('./app/Lab').then((module) => ({ default: module.LabPage })))
const ToolsPage = lazy(() => import('./app/Tools').then((module) => ({ default: module.ToolsPage })))
const ResultsPage = lazy(() => import('./app/Results').then((module) => ({ default: module.ResultsPage })))
const LoginPage = lazy(() => import('./app/Login').then((module) => ({ default: module.LoginPage })))
const PublicWorkspacePage = lazy(() => import('./app/PublicWorkspace').then(module => ({ default: module.PublicWorkspacePage })))
const RegisterPage = lazy(() => import('./app/Login').then((module) => ({ default: module.RegisterPage })))
const ResetPasswordPage = lazy(() => import('./app/Login').then((module) => ({ default: module.ResetPasswordPage })))
const AccountPage = lazy(() => import('./app/Account').then((module) => ({ default: module.AccountPage })))
const ResearchPage = lazy(() => import('./app/Research').then((module) => ({ default: module.ResearchPage })))
const FAQPage = lazy(() => import('./app/FAQ').then((module) => ({ default: module.FAQPage })))
const GuidePage = lazy(() => import('./app/Guide').then((module) => ({ default: module.GuidePage })))
const AutopilotPage = lazy(() => import('./app/Autopilot').then((module) => ({ default: module.AutopilotPage })))
const BotsPage = lazy(() => import('./app/Bots').then((module) => ({ default: module.BotsPage })))
const BotDetailPage = lazy(() => import('./app/BotDetail').then((module) => ({ default: module.BotDetailPage })))
const InboxPage = lazy(() => import('./app/Inbox').then((module) => ({ default: module.InboxPage })))
const ExtensionCenter = lazy(() => import('./features/registry/ExtensionCenter').then((module) => ({ default: module.ExtensionCenter })))

function RouteFallback() {
  const { t } = useI18n()
  return <div className="p-6 text-sm text-muted-foreground" role="status">{t.common.loading}</div>
}

function AuthHandler() {
  const navigate = useNavigate()
  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearAuthenticatedBrowserState(queryClient)
      navigate('/login')
    })
  }, [navigate])
  return null
}

/** Old bookmarks share the one research decision-record page. */
function TimelineRedirect() {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  params.set('tab', 'timeline')
  return <Navigate replace to={`/research?${params.toString()}`} />
}

function LanguageSync() {
  const language = useAppStore((s) => s.language)

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  return null
}

function ThemeSync() {
  const themePreference = useAppStore((s) => s.themePreference)

  useEffect(() => {
    applyTheme(resolveTheme(themePreference))
    if (themePreference !== 'system') return
    return watchSystemTheme(applyTheme)
  }, [themePreference])

  return null
}

const railRoutes = ['/research', '/workflow', '/candidates', '/lab', '/results']

export function AppShell() {
  const copilotOpen = useAppStore((s) => s.copilotOpen)
  const setCopilotOpen = useAppStore((s) => s.setCopilotOpen)
  const copilotSelectedEntityIds = useAppStore((s) => s.copilotSelectedEntityIds)
  const appMode = useAppStore((s) => s.appMode)
  const setAppMode = useAppStore((s) => s.setAppMode)
  const location = useLocation()
  const { projectId, activeProject } = useProjectContext()
  useProjectEvents(activeProject ? projectId : null)
  const showRail = Boolean(activeProject) && railRoutes.some((route) => location.pathname.startsWith(route))
  // `<main>` is the scroll container and outlives every route, so without this a
  // new page opens at whatever depth the previous one was scrolled to.
  const mainRef = useRef<HTMLElement>(null)
  useEffect(() => {
    if (mainRef.current) mainRef.current.scrollTop = 0
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
  }, [location.pathname])

  useEffect(() => {
    if (appMode === 'demo' && activeProject && !isDemoProject(activeProject)) {
      setAppMode('application')
    }
  }, [activeProject, appMode, setAppMode])

  const pageContext = useMemo(() => {
    const search = new URLSearchParams(location.search)
    const entries = [
      `route=${location.pathname}`,
      `query=${location.search || 'none'}`,
      `project_id=${projectId || 'none'}`,
      `name=${activeProject?.name ?? 'unknown'}`,
      `project_type=${activeProject?.project_type ?? 'unknown'}`,
      `project_status=${activeProject?.status ?? 'unknown'}`,
    ]
    if (location.pathname === '/research') {
      entries.push(`research_tab=${search.get('tab') || 'goals'}`)
      entries.push(...copilotSelectedEntityIds.map((entityId) => `entity=${encodeURIComponent(entityId)}`))
    }
    if (activeProject?.summary) {
      entries.push(`project_summary=${activeProject.summary}`)
    }
    return entries.join('; ')
  }, [activeProject, copilotSelectedEntityIds, location.pathname, location.search, projectId])

  return (
    <div
      data-slot="app-shell"
      className="flex min-h-screen min-w-0 flex-col bg-background text-foreground"
    >
      <Topbar />
      <PublicWorkspaceNotice />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <main ref={mainRef} className="min-h-0 min-w-0 flex-1 overflow-y-auto">
          {showRail ? <PipelineRail /> : null}
          <div className="app-content mx-auto max-w-[1600px] px-6 py-6">
            <ErrorBoundary key={`${location.pathname}:${projectId}`}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
        <CopilotDrawer open={copilotOpen} onClose={() => setCopilotOpen(false)} pageContext={pageContext} />
      </div>
      <Toast />
      <AppSettingsDrawer />
      <ActivityDrawer />
      <TourOverlay />
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        <AuthHandler />
        <LanguageSync />
        <ThemeSync />
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route index element={<Navigate to="/projects" replace />} />
            <Route path="/public" element={<PublicWorkspacePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/guide" element={<GuidePage />} />
            <Route element={<WorkspaceAccessGate />}>
              <Route element={<AppShell />}>
                <Route path="/projects" element={<ExperimentsPage />} />
                <Route path="/account" element={<AccountPage />} />
                <Route path="/inbox" element={<InboxPage />} />
                <Route path="/extensions" element={<ExtensionCenter />} />
                <Route path="/bots" element={<BotsPage />} />
                <Route path="/bots/:botId" element={<BotDetailPage />} />
                {/* The page was always labelled "Projects"; only the URL said
                    otherwise. Kept as a redirect so existing links and
                    bookmarks still land, rather than 404ing on a rename. */}
                <Route path="/experiments" element={<Navigate to="/projects" replace />} />
                <Route path="/workflow" element={<ProjectRequired><WorkflowPage /></ProjectRequired>} />
                <Route path="/candidates" element={<ProjectRequired><CandidatesPage /></ProjectRequired>} />
                <Route path="/tools" element={<ToolsPage />} />
                <Route path="/lab" element={<ProjectRequired><LabPage /></ProjectRequired>} />
                <Route path="/learning" element={<ProjectRequired><LearningPage /></ProjectRequired>} />
                <Route path="/results" element={<ProjectRequired><ResultsPage /></ProjectRequired>} />
                <Route path="/research" element={<ProjectRequired><ResearchPage /></ProjectRequired>} />
                <Route path="/timeline" element={<TimelineRedirect />} />
                <Route path="/autopilot" element={<ProjectRequired><AutopilotPage /></ProjectRequired>} />
                <Route path="/faq" element={<FAQPage />} />
                <Route path="*" element={<WorkspaceNotFound />} />
              </Route>
            </Route>
          </Routes>
        </Suspense>
      </HashRouter>
    </QueryClientProvider>
  )
}

function WorkspaceNotFound() {
  const { language } = useI18n()
  const navigate = useNavigate()
  return <section className="space-y-4 py-8">
    <h1 className="text-2xl font-semibold">{language === 'zh' ? '页面不存在' : 'Page not found'}</h1>
    <p className="text-muted-foreground">{language === 'zh' ? '链接可能已过期，请从项目或顶部导航继续。' : 'This link may be outdated. Continue from your projects or the navigation above.'}</p>
    <Button type="button" variant="outline" onClick={() => navigate('/projects', { replace: true })}>{language === 'zh' ? '返回项目' : 'Back to projects'}</Button>
  </section>
}
