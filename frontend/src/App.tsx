import { HashRouter, Navigate, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useMemo } from 'react'
import { Topbar } from './components/ui/Topbar'
import { PipelineRail } from './components/ui/PipelineRail'
import { Toast } from './components/ui/Toast'
import { CopilotDrawer } from './components/ui/CopilotDrawer'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { AppSettingsDrawer } from './components/ui/AppSettingsDrawer'
import { ActivityDrawer } from './features/operations/ActivityDrawer'
import { ProjectRequired } from './features/projects/ProjectRequired'
import { ApiError, setUnauthorizedHandler } from './lib/api/client'
import { useProjectContext } from './lib/hooks/useProjectContext'
import { useAppStore } from './lib/store/appStore'
import { applyTheme, resolveTheme, watchSystemTheme } from './lib/theme/initTheme'
import { isDemoProject, TourOverlay } from './features/tour'
import { clearAuthenticatedBrowserState } from './lib/auth/browserSession'

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
const LabPage = lazy(() => import('./app/Lab').then((module) => ({ default: module.LabPage })))
const ResultsPage = lazy(() => import('./app/Results').then((module) => ({ default: module.ResultsPage })))
const LoginPage = lazy(() => import('./app/Login').then((module) => ({ default: module.LoginPage })))
const ResearchPage = lazy(() => import('./app/Research').then((module) => ({ default: module.ResearchPage })))
const TimelinePage = lazy(() => import('./app/Timeline'))
const FAQPage = lazy(() => import('./app/FAQ').then((module) => ({ default: module.FAQPage })))
const GuidePage = lazy(() => import('./app/Guide').then((module) => ({ default: module.GuidePage })))
const AutopilotPage = lazy(() => import('./app/Autopilot').then((module) => ({ default: module.AutopilotPage })))

function RouteFallback() {
  return <div className="p-6 text-sm text-muted-foreground" role="status">Loading…</div>
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

function RequireAuth() {
  const token = sessionStorage.getItem('bda_token')
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
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
  const showRail = Boolean(activeProject) && railRoutes.some((route) => location.pathname.startsWith(route))

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
      entries.push(`research_tab=${search.get('tab') || 'evidence'}`)
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
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
          {showRail ? <PipelineRail /> : null}
          <div className="mx-auto max-w-[1480px] px-6 py-6">
            <ErrorBoundary>
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
            <Route path="/login" element={<LoginPage />} />
            <Route path="/guide" element={<GuidePage />} />
            <Route element={<RequireAuth />}>
              <Route element={<AppShell />}>
                <Route index element={<Navigate to="/projects" replace />} />
                <Route path="/projects" element={<ExperimentsPage />} />
                {/* The page was always labelled "Projects"; only the URL said
                    otherwise. Kept as a redirect so existing links and
                    bookmarks still land, rather than 404ing on a rename. */}
                <Route path="/experiments" element={<Navigate to="/projects" replace />} />
                <Route path="/workflow" element={<ProjectRequired><WorkflowPage /></ProjectRequired>} />
                <Route path="/candidates" element={<ProjectRequired><CandidatesPage /></ProjectRequired>} />
                <Route path="/lab" element={<ProjectRequired><LabPage /></ProjectRequired>} />
                <Route path="/results" element={<ProjectRequired><ResultsPage /></ProjectRequired>} />
                <Route path="/research" element={<ResearchPage />} />
                <Route path="/timeline" element={<ProjectRequired><TimelinePage /></ProjectRequired>} />
                <Route path="/autopilot" element={<ProjectRequired><AutopilotPage /></ProjectRequired>} />
                <Route path="/faq" element={<FAQPage />} />
              </Route>
            </Route>
          </Routes>
        </Suspense>
      </HashRouter>
    </QueryClientProvider>
  )
}
