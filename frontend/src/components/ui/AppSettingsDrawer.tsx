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
import {
  CopilotSettings,
  type CopilotSettingsActions,
} from '../../features/copilot/CopilotSettings'
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
  const [copilotActions, setCopilotActions] = useState<CopilotSettingsActions | null>(null)
  const backend = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    enabled: settingsOpen,
  })
  const cluster = useQuery({
    queryKey: ['cluster-health'],
    queryFn: getClusterHealth,
    enabled: settingsOpen,
    retry: false,
  })
  const copilotConfig = useQuery({
    queryKey: ['copilot-config', projectId],
    queryFn: () => getCopilotConfig(projectId),
    enabled: settingsOpen && Boolean(projectId),
    retry: false,
  })

  const refreshConnections = () => {
    void backend.refetch()
    void cluster.refetch()
    void copilotConfig.refetch()
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
            <p className="text-sm text-text-secondary">{t.settings.description}</p>
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
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => setSettingsOpen(false)}>
            {t.settings.cancel}
          </Button>
          <Button type="button"
            variant="outline"
            disabled={!copilotActions?.canTest || copilotActions.testPending}
            onClick={() => copilotActions?.test()}
          >
            {t.settings.testApi}
          </Button>
          <Button type="button"
            variant="default"
            disabled={!copilotActions?.canSave || copilotActions.savePending}
            onClick={() => copilotActions?.save()}
          >
            {t.settings.save}
          </Button>
        </div>
      }
    >
      <div data-tour-id="settings-drawer">
      <section className="space-y-3 border-b border-border-soft p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <GearIcon className="h-4 w-4 text-accent" />
          {t.settings.operatingMode}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button
            type="button"
            variant={appMode === 'application' ? 'secondary' : 'outline'}
            className={clsx(
              'h-auto flex-col items-start p-3 text-left',
            )}
            onClick={() => setAppMode('application')}
          >
            <strong className="block text-sm">{t.settings.applicationMode}</strong>
            <span className="mt-1 block text-xs text-text-secondary">{t.settings.applicationModeBody}</span>
          </Button>
          <Button
            type="button"
            variant={appMode === 'demo' ? 'secondary' : 'outline'}
            className={clsx(
              'h-auto flex-col items-start p-3 text-left',
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
      </section>

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
          connected={backend.isSuccess}
          detail={backend.data ? Object.entries(backend.data.checks ?? {}).map(([name, status]) => `${name}: ${status}`).join(' · ') || backend.data.service || backend.data.status : backend.error instanceof Error ? backend.error.message : t.settingsExt.connections.awaitingValidation}
        />
        <ConnectionRow
          label={t.settingsExt.connections.lsf}
          connected={cluster.data?.connected === true}
          detail={
            cluster.data?.connected
              ? format(t.settingsExt.connections.queueHost, {
                  host: cluster.data.host ?? 'qm',
                  count: cluster.data.queues.length,
                })
              : cluster.data?.reason ?? t.settingsExt.connections.awaitingValidation
          }
        />
        <ConnectionRow
          label={t.settingsExt.connections.openai}
          connected={copilotConfig.data?.api_key_configured === true}
          detail={
            copilotConfig.data?.api_key_configured
              ? `${copilotConfig.data.llm_model} · ${t.settingsExt.connections.configured}`
              : t.settingsExt.connections.apiKeyNotConfigured
          }
        />
      </section>

      <ComputeTargetsSection />
      <AdministrationSections />

      <section className="space-y-3 border-b border-border-soft p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <MapPinIcon className="h-4 w-4 text-accent" />
          {t.guide.settings.sectionTitle}
        </div>
        <p className="text-xs text-text-secondary">
          {language === 'zh' ? '继续或重新开始交互式界面操作导览。' : 'Continue or restart the interactive interface tour.'}
        </p>
        <div className="flex gap-2">
          {tourState.status === 'paused' ? <Button type="button" size="sm" variant="outline" onClick={() => { const demo = findDemoProject(projects); if (!demo) return; setAppMode('demo'); setProjectId(demo.id); setSettingsOpen(false); resumeTour() }}>{language === 'zh' ? '继续导览' : 'Continue tour'}</Button> : null}
          <Button type="button" size="sm" variant="ghost" onClick={() => { const demo = findDemoProject(projects); if (!demo) return; setAppMode('demo'); setProjectId(demo.id); setSettingsOpen(false); restartTour() }}>{language === 'zh' ? '重新开始' : 'Restart tour'}</Button>
        </div>
      </section>

      <section className="space-y-3 border-b border-border-soft p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <MapPinIcon className="h-4 w-4 text-accent" />
          {t.guide.settings.sectionTitle}
        </div>
        <p className="text-xs text-text-secondary">{t.guide.settings.sectionBody}</p>
        <Link
          to="/guide"
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-accent-border bg-accent-bg px-4 py-2.5 text-sm font-medium text-accent transition-colors hover:border-accent hover:bg-accent-bg"
          onClick={() => setSettingsOpen(false)}
        >
          <MapPinIcon className="h-4 w-4" aria-hidden="true" />
          {t.guide.settings.openGuide}
        </Link>
      </section>

      <section className="space-y-2 border-b border-border-soft p-4">
        <p className="text-sm font-medium text-text-primary">{t.settings.appearance}</p>
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

      <CopilotSettings hideActions onActionsReady={setCopilotActions} />
      </div>
    </DrawerShell>
  )
}

function ConnectionRow({ label, connected, detail }: { label: string; connected: boolean; detail: string }) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const isLongError = !connected && detail.length > 48

  return (
    <div className="rounded-xl border border-border-soft bg-bg-app px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <strong className="text-sm text-text-primary">{label}</strong>
        <StatusBadge
          status={connected ? 'success' : 'danger'}
          label={connected ? t.shared.status.connected : t.shared.status.disconnected}
        />
      </div>
      {isLongError ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mt-1"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? <CaretDownIcon className="h-3 w-3" /> : <CaretRightIcon className="h-3 w-3" />}
          {expanded ? detail : t.settingsExt.connectionRow.showDetails}
        </Button>
      ) : (
        <p className="mt-1 text-xs text-text-secondary">{detail}</p>
      )}
    </div>
  )
}
