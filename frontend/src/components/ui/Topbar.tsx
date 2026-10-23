import { useRef } from 'react'
import { NavLink, useNavigate } from 'react-router'
import { DotsThreeIcon, PulseIcon, FoldersIcon, ChatCircleIcon, FlaskIcon, GearIcon } from '@phosphor-icons/react'
import { useI18n } from '../../lib/i18n'
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
import { StatusBadge } from './statusBadge'
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuTrigger } from './dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './select'

export function Topbar() {
  const navigate = useNavigate()
  const utilitiesRef = useRef<HTMLButtonElement>(null)
  const openUtility = (open: () => void) => {
    // The menu item unmounts on selection. Give the drawer a stable focus return target.
    utilitiesRef.current?.focus()
    open()
  }
  const { appMode, copilotOpen, setCopilotOpen, setSettingsOpen, activityOpen, setActivityOpen, setTourMenuOpen } = useAppStore()
  const { t, language } = useI18n()
  const { visibleProjects, activeProject, projectId, setProjectId } = useProjectContext()
  const projectQuery = projectId ? `?project=${encodeURIComponent(projectId)}` : ''

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
          <div className="topbar-help"><HelpMenu /></div>
          <div className="science-mobile-utilities">
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button ref={utilitiesRef} type="button" variant="ghost" size="icon" />} aria-label={language === 'zh' ? '更多工作区操作' : 'More workspace actions'}><DotsThreeIcon aria-hidden="true" /></DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="science-utility-menu w-64">
                <DropdownMenuGroup>
                  <DropdownMenuItem onClick={() => openUtility(() => setActivityOpen(!activityOpen))}><PulseIcon aria-hidden="true" />{t.operations.toggleTitle}</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => openUtility(() => setSettingsOpen(true))}><GearIcon aria-hidden="true" />{t.shared.applicationSettings}</DropdownMenuItem>
                  <DropdownMenuItem className="min-[375px]:hidden" onClick={() => openUtility(() => setTourMenuOpen(true))}>{language === 'zh' ? '界面导览' : 'Interface tour'}</DropdownMenuItem>
                  <DropdownMenuItem className="min-[375px]:hidden" onClick={() => navigate(`/guide${projectQuery}`)}>{t.pipeline.workflowGuide}</DropdownMenuItem>
                  <DropdownMenuItem className="min-[375px]:hidden" onClick={() => navigate(`/faq${projectQuery}`)}>{t.nav.faq}</DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <Button
            type="button"
            data-tour-id="copilot-launcher"
            aria-label={t.copilot.drawer.toggleTitle}
            aria-expanded={copilotOpen}
            aria-haspopup="dialog"
            title={t.copilot.drawer.toggleTitle}
            variant={copilotOpen ? 'secondary' : 'outline'}
            className="copilot-launcher"
            onClick={() => setCopilotOpen(!copilotOpen)}
          >
            <ChatCircleIcon aria-hidden="true" />
            <span className="hidden sm:inline">Bot</span>
          </Button>
          <CommandPalette />
          <div className="science-desktop-utilities">
          <span className="hidden sm:inline-flex">
            <StatusBadge
              status={appMode === 'application' ? 'info' : 'warning'}
              label={appMode === 'application' ? t.settingsExt.applicationModeBadge : t.demoMode}
            />
          </span>
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

      <BackendHealthBanner />
      </div>
    </>
  )
}
