import { Link, NavLink, useLocation, useNavigate } from 'react-router'
import clsx from 'clsx'
import { DotsThreeIcon, PulseIcon, BooksIcon, FoldersIcon, RobotIcon, ChatCircleIcon, FlaskIcon, GearIcon, ListChecksIcon, WrenchIcon } from '@phosphor-icons/react'
import { useI18n } from '../../lib/i18n'
import { APP_ROUTES, PRIMARY_ROUTES, routeLabel, workbenchGroups, type AppRoute } from '../../lib/nav/routes'
import { CommandPalette } from './CommandPalette'
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
import { BigoBioLogo } from './BigoBioLogo'
import { isPublicVisitor } from '../../lib/auth/publicWorkspace'
import { StatusBadge } from './statusBadge'
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from './dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './select'

// The route list moved to `lib/nav/routes.ts` when the command palette began
// needing the same one: two copies of "which routes exist and what they are
// called" drift silently, because renaming one of them breaks nothing.
const mobileRoutes = APP_ROUTES.filter(route => route.to !== '/workflow')
const primaryRoutes = PRIMARY_ROUTES

export function Topbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { appMode, copilotOpen, setCopilotOpen, setSettingsOpen, activityOpen, setActivityOpen } = useAppStore()
  const { t, language } = useI18n()
  const { visibleProjects, activeProject, projectId, setProjectId } = useProjectContext()
  const projectQuery = projectId ? `?project=${encodeURIComponent(projectId)}` : ''
  const zh = language === 'zh'
  const workflowResource = new URLSearchParams(location.search).get('resource')
  const coreLinks = [
    { resource: '', label: zh ? '工作流' : 'Workflow' },
    { resource: 'plugins', label: zh ? '模型插件' : 'Models & plugins' },
    { resource: 'scripts', label: zh ? '脚本' : 'Scripts' },
  ]
  const coreHref = (resource: string) => {
    const params = new URLSearchParams(location.pathname === '/workflow' ? location.search : projectQuery)
    if (projectId) params.set('project', projectId)
    if (resource) params.set('resource', resource)
    else params.delete('resource')
    return `/workflow${params.size ? `?${params}` : ''}`
  }
  const activeWorkbench = APP_ROUTES.find((route) => !PRIMARY_ROUTES.includes(route.to) && location.pathname === route.to)
  const navLabel = (key: AppRoute['key']) => routeLabel(key, zh, (item) => t.nav[item])

  return (
    <>
      <div className="sticky top-0 z-40">
      <header className="science-topbar flex flex-wrap items-center gap-2 border-b border-border-soft bg-bg-app/95 px-4 py-2.5 backdrop-blur sm:flex-nowrap lg:gap-3 lg:px-6">
        <NavLink
          to={`/projects${projectQuery}`}
          className="science-brand shrink-0 text-sm font-semibold text-text-primary"
        >
          <BigoBioLogo />
          <span className="science-brand-product">{t.brand}</span>
        </NavLink>

        {/* Project is the anchor of the whole workbench: give it a prominent,
            always-visible switcher rather than a buried select. */}
        <div className="order-3 flex min-w-0 basis-full items-center gap-2 sm:order-none sm:basis-auto sm:flex-1">
          {visibleProjects.length > 0 ? (
            <div className="group flex min-w-0 flex-1 max-w-md items-center gap-2" data-tour-id="project-selector">
              <FlaskIcon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="hidden shrink-0 text-fine font-semibold uppercase tracking-wide text-text-muted sm:inline">
                {t.common.project}
              </span>
              <Select
                value={projectId || null}
                items={visibleProjects.map((project) => ({ value: project.id, label: projectText(project, 'name', language) }))}
                onValueChange={(value) => setProjectId(value ?? '')}
              >
                <SelectTrigger aria-label={t.common.selectProject} title={activeProject ? projectText(activeProject, 'name', language) : t.common.selectProject} className="h-10! min-w-0 w-full text-sm!">
                  <SelectValue className="min-w-0" placeholder={t.common.selectProject}>
                    {activeProject ? <span className="truncate">{projectText(activeProject, 'name', language)}</span> : null}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {visibleProjects.map((p) => (
                    <SelectItem key={p.id} value={p.id} className="text-sm" title={projectText(p, 'name', language)}>
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
          {activeProject ? <Button type="button" variant="ghost" size="icon-sm" className="md:hidden" aria-label={t.projects.activeProjectPanel.manageProject} onClick={() => navigate(`/projects${projectQuery}`)}><FoldersIcon aria-hidden="true" /></Button> : null}
        </div>

        <div className="topbar-actions flex min-w-0 shrink-0 items-center gap-1.5 text-xs">
          <HelpMenu />
          <div className="science-mobile-utilities">
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button type="button" variant="ghost" size="icon" />} aria-label={language === 'zh' ? '更多工作区操作' : 'More workspace actions'}><DotsThreeIcon aria-hidden="true" /></DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="science-utility-menu w-64">
                <DropdownMenuGroup>
                  <DropdownMenuItem onClick={() => setCopilotOpen(!copilotOpen)}><ChatCircleIcon aria-hidden="true" />{t.copilot.drawer.toggleTitle}</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setActivityOpen(!activityOpen)}><PulseIcon aria-hidden="true" />{t.operations.toggleTitle}</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setSettingsOpen(true)}><GearIcon aria-hidden="true" />{t.shared.applicationSettings}</DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <div className="science-desktop-utilities">
          <span className="hidden sm:inline-flex">
            <StatusBadge
              status={appMode === 'application' ? 'info' : 'warning'}
              label={isPublicVisitor() ? (zh ? 'Public · 只读' : 'Public · Read only') : appMode === 'application' ? t.settingsExt.applicationModeBadge : t.demoMode}
            />
          </span>
          <Button
            type="button"
            aria-label={t.copilot.drawer.toggleTitle}
            title={t.copilot.drawer.toggleTitle}
            variant={copilotOpen ? 'secondary' : 'ghost'}
            size="icon-sm"
            onClick={() => setCopilotOpen(!copilotOpen)}
          >
            <ChatCircleIcon className="h-4 w-4" />
          </Button>
          <CommandPalette />
          <ActivityIndicatorButton />
          <Button
            type="button"
            aria-label={t.shared.applicationSettings}
            title={t.shared.applicationSettings}
            variant="ghost"
            size="icon-sm"
            onClick={() => setSettingsOpen(true)}
          >
            <GearIcon className="h-4 w-4" />
          </Button>
          </div>
          <UserMenu />
        </div>
      </header>

      {/* Core tools remain visible at every width and while scrolling. */}
      <nav
        data-tour-id="main-navigation"
        aria-label={t.shared.mainNavigation}
        className="science-navigation flex flex-wrap gap-1 border-b border-border-soft bg-bg-app px-3 py-2"
      >
        {mobileRoutes.map((route) => (
          <NavLink
            key={route.to}
            data-nav-route={route.to}
            to={`${route.to}${projectQuery}`}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-2 shrink-0 rounded px-3 py-1.5 text-sm transition-colors',
                !primaryRoutes.includes(route.to) && 'hidden',
                isActive
                  ? 'bg-accent/15 text-accent'
                  : 'text-text-secondary hover:bg-surface-1 hover:text-text-primary',
              )
            }
          >
            {route.to === '/projects' ? <FoldersIcon aria-hidden="true" /> : route.to === '/inbox' ? <ListChecksIcon aria-hidden="true" /> : route.to === '/bots' ? <RobotIcon aria-hidden="true" /> : route.to === '/research' ? <BooksIcon aria-hidden="true" /> : route.to === '/tools' ? <FlaskIcon aria-hidden="true" /> : null}
            {navLabel(route.key)}
          </NavLink>
        ))}
        {coreLinks.map(({ resource, label }) => {
          const active = location.pathname === '/workflow' && (workflowResource || '') === resource
          return <Link key={resource} data-nav-route={resource ? `/workflow?resource=${resource}` : '/workflow'} to={coreHref(resource)} aria-current={active ? 'page' : undefined} className={clsx('flex shrink-0 items-center rounded px-3 py-1.5 text-sm transition-colors', active ? 'bg-accent/15 text-accent' : 'text-text-secondary hover:bg-surface-1 hover:text-text-primary')}>{label}</Link>
        })}
        <div className="flex items-stretch">
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button type="button" variant="ghost" size="sm" className="nav-workbenches" aria-current={activeWorkbench ? 'true' : undefined} />}><WrenchIcon aria-hidden="true" />{activeWorkbench ? navLabel(activeWorkbench.key) : zh ? '工作台' : 'Workbenches'}</DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              {workbenchGroups(zh).map((group) => <DropdownMenuGroup key={group.key}>
                <DropdownMenuLabel>{group.label}</DropdownMenuLabel>
                {group.routes.map((route) => (
                  <DropdownMenuItem key={route.to} onClick={() => navigate(`${route.to}${projectQuery}`)}>{navLabel(route.key)}</DropdownMenuItem>
                ))}
              </DropdownMenuGroup>)}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </nav>
      </div>
      <BackendHealthBanner />
    </>
  )
}
