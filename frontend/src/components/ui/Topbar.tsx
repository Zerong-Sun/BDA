import { NavLink, useNavigate } from 'react-router'
import clsx from 'clsx'
import { ChatCircleIcon, FlaskIcon, GearIcon, QuestionIcon } from '@phosphor-icons/react'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useAppStore } from '../../lib/store/appStore'
import { projectText } from '../../lib/i18n/projectText'
import { BackendHealthBanner } from './BackendHealthBanner'
import { ActivityIndicatorButton } from '../../features/operations/ActivityIndicatorButton'
import { UserMenu } from './UserMenu'
import { HelpMenu } from './HelpMenu'
import { StatusPill } from './StatusPill'
import { statusTone } from './statusTone'
import { Button } from './Button'
import { StatusBadge } from './statusBadge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './select'

const mobileRoutes = [
  { to: '/projects', key: 'projects' as const },
  { to: '/research', key: 'research' as const },
  { to: '/workflow', key: 'workflow' as const },
  { to: '/candidates', key: 'candidates' as const },
  { to: '/lab', key: 'lab' as const },
  { to: '/results', key: 'results' as const },
  { to: '/timeline', key: 'timeline' as const },
  { to: '/faq', key: 'faq' as const },
]

export function Topbar() {
  const navigate = useNavigate()
  const { appMode, copilotOpen, setCopilotOpen, setSettingsOpen, setTourMenuOpen } = useAppStore()
  const { t, language } = useI18n()
  const { visibleProjects, activeProject, projectId, setProjectId } = useProjectContext()
  const projectQuery = projectId ? `?project=${encodeURIComponent(projectId)}` : ''

  return (
    <>
      <header className="sticky top-0 z-40 flex flex-wrap items-center gap-2 border-b border-border-soft bg-bg-app/95 px-4 py-2.5 backdrop-blur sm:flex-nowrap lg:gap-3 lg:px-6">
        <NavLink
          to={`/projects${projectQuery}`}
          className="shrink-0 text-sm font-semibold text-text-primary"
        >
          {t.brand}
        </NavLink>

        {/* Project is the anchor of the whole workbench: give it a prominent,
            always-visible switcher rather than a buried select. */}
        <div className="order-3 flex min-w-0 basis-full items-center gap-2 sm:order-none sm:basis-auto sm:flex-1">
          {visibleProjects.length > 0 ? (
            <div className="group flex min-w-0 max-w-sm items-center gap-2" data-tour-id="project-selector">
              <FlaskIcon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="hidden shrink-0 text-fine font-semibold uppercase tracking-wide text-text-muted sm:inline">
                {t.common.project}
              </span>
              <Select value={projectId || null} onValueChange={(value) => setProjectId(value ?? '')}>
                <SelectTrigger aria-label={t.common.selectProject} className="min-w-48 max-w-sm">
                  <SelectValue placeholder={t.common.selectProject} />
                </SelectTrigger>
                <SelectContent>
                  {visibleProjects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {projectText(p, 'name', language)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <span className="truncate text-xs text-text-muted">{t.common.selectProject}</span>
          )}
          {activeProject ? (
            <span className="hidden lg:inline">
              <StatusPill label={activeProject.status} tone={statusTone(activeProject.status)} />
            </span>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-1.5 text-xs">
          <span className="hidden sm:inline-flex">
            <StatusBadge
              status={appMode === 'application' ? 'info' : 'warning'}
              label={appMode === 'application' ? t.settingsExt.applicationModeBadge : t.demoMode}
            />
          </span>
          <span className="hidden sm:inline-flex">
            <HelpMenu />
          </span>
          <Button
            data-tour-id="tour-help"
            type="button"
            aria-label={language === 'zh' ? '打开界面导览' : 'Open interface tour'}
            title={language === 'zh' ? '界面导览' : 'Interface tour'}
            variant="outline"
            size="icon-sm"
            onClick={() => setTourMenuOpen(true)}
          >
            <QuestionIcon className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            aria-label={t.copilot.drawer.toggleTitle}
            title={t.copilot.drawer.toggleTitle}
            variant={copilotOpen ? 'secondary' : 'outline'}
            size="icon-sm"
            onClick={() => setCopilotOpen(!copilotOpen)}
          >
            <ChatCircleIcon className="h-4 w-4" />
          </Button>
          <ActivityIndicatorButton />
          <Button
            type="button"
            aria-label={t.shared.applicationSettings}
            title={t.shared.applicationSettings}
            variant="outline"
            size="icon-sm"
            onClick={() => setSettingsOpen(true)}
          >
            <GearIcon className="h-4 w-4" />
          </Button>
          <UserMenu />
        </div>
      </header>

      {/* On small screens the pipeline rail collapses, so the topbar keeps a
          full route list for reachability (and for accessibility tests). */}
      <nav
        aria-label={t.shared.mainNavigation}
        className="flex gap-1 overflow-x-auto border-b border-border-soft bg-bg-app px-3 py-2 md:hidden"
      >
        {mobileRoutes.map((route) => (
          <NavLink
            key={route.to}
            to={`${route.to}${projectQuery}`}
            className={({ isActive }) =>
              clsx(
                'shrink-0 rounded-lg px-3 py-1.5 text-sm transition-colors',
                isActive
                  ? 'bg-accent/15 text-accent'
                  : 'text-text-secondary hover:bg-surface-1 hover:text-text-primary',
              )
            }
          >
            {t.nav[route.key]}
          </NavLink>
        ))}
      </nav>
      {activeProject ? (
        <div className="border-b border-border-soft bg-bg-canvas px-4 py-1.5 text-xs text-text-secondary md:hidden">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={t.projects.activeProjectPanel.manageProject}
            className="truncate"
            onClick={() => navigate(`/projects${projectQuery}`)}
          >
            {projectText(activeProject, 'name', language)}
          </Button>
        </div>
      ) : null}
      <BackendHealthBanner />
    </>
  )
}
