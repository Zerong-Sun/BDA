import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  ArrowsClockwiseIcon,
  CaretDownIcon,
  CaretRightIcon,
  GearIcon,
  MapPinIcon,
  HardDrivesIcon,
  XIcon,
} from '@phosphor-icons/react'
import { Link } from 'react-router'
import { CopilotSettings } from '../../features/copilot/CopilotSettings'
import { isPublicVisitor } from '../../lib/auth/publicWorkspace'
import { PrivateAccessLinks } from '../../features/account/PrivateAccessLinks'
import { useAuthConfig } from '../../lib/auth/account'
import { managesProject, useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { getCopilotConfig } from '../../lib/api/copilot'
import { getClusterHealth } from '../../lib/api/registry'
import { getHealth } from '../../lib/api/health'
import { useAppStore, type ThemePreference } from '../../lib/store/appStore'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { AdministrationSections } from './AdministrationSections'
import { ComputeTargetsSection } from './ComputeTargetsSection'
import { useI18n } from '../../lib/i18n'
import { DrawerShell } from './DrawerShell'
import { Button } from './Button'
import { applyTheme, resolveTheme } from '../../lib/theme/initTheme'
import { findDemoProject } from '../../features/tour'
import { StatusBadge } from './statusBadge'

export function AppSettingsDrawer() {
  const { t, format, language } = useI18n()
  const { settingsOpen, setSettingsOpen, appMode, setAppMode, themePreference, setThemePreference, tourState, resumeTour, restartTour } = useAppStore()
  const { projects, projectId, setProjectId } = useProjectContext()
  const guest = isPublicVisitor()
  const authConfig = useAuthConfig()
  const access = useProjectAccess(projectId)
  const canManage = !guest && managesProject(access.data)
  const backend = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    enabled: settingsOpen,
  })
  const cluster = useQuery({
    queryKey: ['cluster-health'],
    queryFn: getClusterHealth,
    enabled: settingsOpen && !guest,
    retry: false,
  })
  const copilotConfig = useQuery({
    queryKey: ['copilot-config', projectId],
    queryFn: () => getCopilotConfig(projectId),
    enabled: settingsOpen && Boolean(projectId) && canManage,
    retry: false,
  })

  const refreshConnections = () => {
    void backend.refetch()
    if (!guest) void cluster.refetch()
    if (projectId && canManage) void copilotConfig.refetch()
  }

  const setTheme = (pref: ThemePreference) => {
    setThemePreference(pref)
    applyTheme(resolveTheme(pref))
  }

  return (
    <DrawerShell
      open={settingsOpen}
      onClose={() => setSettingsOpen(false)}
      widthClass="sm:max-w-[30rem]"
      title={t.settings.title}
      header={
        <div className="flex w-full items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-accent">{t.settings.title}</p>
            <h2 className="text-lg font-semibold text-text-primary">{t.settings.subtitle}</h2>
            <p className="text-sm text-text-secondary">{guest ? (language === 'zh' ? '外观、使用帮助与 Private 入口' : 'Appearance, help and Private access') : t.settings.description}</p>
          </div>
          <Button
            type="button"
            aria-label={t.settingsExt.closeAriaLabel}
            variant="ghost"
            size="icon-sm"
            onClick={() => setSettingsOpen(false)}
          >
            <XIcon aria-hidden="true" />
          </Button>
        </div>
      }
      footer={<Button type="button" variant="outline" onClick={() => setSettingsOpen(false)}>{language === 'zh' ? '完成' : 'Done'}</Button>}
    >
      <div data-tour-id="settings-drawer">
      <section className="border-b border-border-soft p-4">
        {guest ? <PrivateAccessLinks config={authConfig.data} /> : <Link to="/account" onClick={() => setSettingsOpen(false)} className="text-sm font-medium text-primary underline underline-offset-4">{language === 'zh' ? '账号与访问：密码、邀请和工作区入口' : 'Account & access: password, invitations and workspaces'}</Link>}
      </section>
      {!guest ? <section className="space-y-3 border-b border-border-soft p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <GearIcon className="h-4 w-4 text-accent" />
          {t.settings.operatingMode}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button
            type="button"
            variant={appMode === 'application' ? 'secondary' : 'outline'}
            className={clsx(
              'h-auto min-w-0 whitespace-normal break-words flex-col items-start p-3 text-left',
            )}
            onClick={() => setAppMode('application')}
          >
            <strong className="block text-sm">{t.settings.applicationMode}</strong>
            <span className="mt-1 block text-xs text-text-secondary">{t.settings.applicationModeBody}</span>
          </Button>
          <Button
            type="button"
            variant={appMode === 'demo' ? 'secondary' : 'outline'}
            disabled={!findDemoProject(projects)}
            className={clsx(
              'h-auto min-w-0 whitespace-normal break-words flex-col items-start p-3 text-left',
            )}
            onClick={() => {
              const preferred = findDemoProject(projects)
              if (preferred) {
                setAppMode('demo')
                setProjectId(preferred.id)
              }
            }}
          >
            <strong className="block text-sm">{t.settings.demoMode}</strong>
            <span className="mt-1 block text-xs text-text-secondary">{t.settings.demoModeBody}</span>
          </Button>
        </div>
      </section> : null}

      <section className="space-y-3 border-b border-border-soft p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium">
            <HardDrivesIcon className="h-4 w-4 text-accent" />
            {t.settings.connections}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={refreshConnections}
          >
            <ArrowsClockwiseIcon className={`h-3.5 w-3.5 ${backend.isFetching || cluster.isFetching ? 'animate-spin' : ''}`} />
            {t.settings.revalidate}
          </Button>
        </div>
        <ConnectionRow
          label={t.settingsExt.connections.backend}
          connected={backend.data?.status === 'ok'}
          detail={backend.data ? Object.entries(backend.data.checks ?? {}).map(([name, status]) => `${name}: ${status}`).join(' · ') || backend.data.service || backend.data.status : backend.error instanceof Error ? backend.error.message : t.settingsExt.connections.awaitingValidation}
        />
        {!guest ? <ConnectionRow
          label={t.settingsExt.connections.lsf}
          connected={cluster.data?.connected === true}
          detail={
            cluster.data?.connected
              ? format(t.settingsExt.connections.queueHost, {
                  host: cluster.data.host ?? 'LSF',
                  count: cluster.data.queues.length,
                })
              : cluster.data?.reason ?? t.settingsExt.connections.awaitingValidation
          }
        /> : null}
        {canManage ? <ConnectionRow
          label={t.settingsExt.connections.openai}
          connected={false}
          configured={copilotConfig.data?.api_key_configured === true}
          detail={
            copilotConfig.data?.api_key_configured
              ? `${copilotConfig.data.llm_model} · ${t.settingsExt.connections.configured}`
              : t.settingsExt.connections.apiKeyNotConfigured
          }
        /> : null}
      </section>

      {!guest ? <><ComputeTargetsSection /><AdministrationSections /></> : null}

      <section className="space-y-3 border-b border-border-soft p-4">
        <h3 className="flex items-center gap-2 text-sm font-medium"><MapPinIcon className="h-4 w-4 text-accent" />{t.guide.settings.sectionTitle}</h3>
        <p className="text-xs text-text-secondary">{t.guide.settings.sectionBody}</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" render={<Link to={`/guide${projectId ? `?project=${encodeURIComponent(projectId)}` : ''}`} />} onClick={() => setSettingsOpen(false)}>{t.guide.settings.openGuide}</Button>
          {findDemoProject(projects) ? <Button type="button" variant="ghost" onClick={() => {
            const demo = findDemoProject(projects)
            if (!demo) return
            setAppMode('demo'); setProjectId(demo.id); setSettingsOpen(false)
            if (tourState.status === 'paused') resumeTour()
            else restartTour()
          }}>{tourState.status === 'paused' ? (language === 'zh' ? '继续导览' : 'Continue tour') : (language === 'zh' ? '交互导览' : 'Interactive tour')}</Button> : null}
        </div>
      </section>

      <section className="space-y-2 border-b border-border-soft p-4">
        <p className="text-sm font-medium text-text-primary">{t.settings.appearance}</p>
        <p className="text-xs text-text-secondary">{language === 'zh' ? '外观设置即时生效，仅保存在此浏览器。' : 'Appearance changes apply immediately and are saved in this browser.'}</p>
        <div className="flex flex-wrap gap-2">
          {(['light', 'dark', 'system'] as const).map((pref) => (
            <Button
              key={pref}
              type="button"
              variant={themePreference === pref ? 'secondary' : 'outline'}
              size="sm"
              className={clsx(
                'capitalize',
              )}
              onClick={() => setTheme(pref)}
            >
              {t.settings.theme[pref]}
            </Button>
          ))}
        </div>
      </section>

      {canManage ? <CopilotSettings /> : null}
      </div>
    </DrawerShell>
  )
}

function ConnectionRow({ label, connected, configured = false, detail }: { label: string; connected: boolean; configured?: boolean; detail: string }) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const isLongError = !connected && detail.length > 48

  return (
    <div className="rounded-xl border border-border-soft bg-bg-app px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <strong className="text-sm text-text-primary">{label}</strong>
        <StatusBadge
          status={connected ? 'success' : configured ? 'info' : 'warning'}
          label={connected ? t.shared.status.connected : configured ? t.settingsExt.connections.configured : t.shared.status.disconnected}
        />
      </div>
      {isLongError ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mt-1 h-auto whitespace-normal break-words text-left"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? <CaretDownIcon className="h-3 w-3" /> : <CaretRightIcon className="h-3 w-3" />}
          {expanded ? detail : t.settingsExt.connectionRow.showDetails}
        </Button>
      ) : (
        <p className="mt-1 break-words text-xs text-text-secondary">{detail}</p>
      )}
    </div>
  )
}
