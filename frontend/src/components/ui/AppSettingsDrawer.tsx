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
import { CopilotSettings, type CopilotSettingsActions } from '../../features/copilot/CopilotSettings'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from './Tabs'

export function AppSettingsDrawer() {
  const { t, format, language } = useI18n()
  const { settingsOpen, setSettingsOpen, appMode, setAppMode, themePreference, setThemePreference, tourState, resumeTour, restartTour } = useAppStore()
  const { projects, projectId, setProjectId } = useProjectContext()
  const guest = isPublicVisitor()
  const authConfig = useAuthConfig()
  const access = useProjectAccess(projectId)
  const canManage = !guest && managesProject(access.data)
  const [section, setSection] = useState('general')
  const [copilotActions, setCopilotActions] = useState<CopilotSettingsActions | null>(null)
  const backend = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    enabled: settingsOpen && section === 'connections',
  })
  const cluster = useQuery({
    queryKey: ['cluster-health'],
    queryFn: getClusterHealth,
    enabled: settingsOpen && section === 'connections' && !guest,
    retry: false,
  })
  const copilotConfig = useQuery({
    queryKey: ['copilot-config', projectId],
    queryFn: () => getCopilotConfig(projectId),
    enabled: settingsOpen && section === 'connections' && Boolean(projectId) && canManage,
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
      footer={
        <div className="flex w-full min-w-0 flex-wrap justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => setSettingsOpen(false)}>
            {language === 'zh' ? '关闭' : 'Close'}
          </Button>
          {section === 'model' && canManage ? <><Button type="button"
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
            {language === 'zh' ? '保存模型配置' : 'Save model configuration'}
          </Button></> : null}
        </div>
      }
    >
      <div data-tour-id="settings-drawer">
      <Tabs value={section} onValueChange={setSection} className="gap-0">
        <TabsList variant="line" className="sticky top-0 z-10 h-11! w-full border-b bg-background px-3">
          <TabsTrigger value="general">{language === 'zh' ? '偏好与帮助' : 'Preferences'}</TabsTrigger>
          {canManage ? <TabsTrigger value="model">{language === 'zh' ? '模型配置' : 'Model'}</TabsTrigger> : null}
          <TabsTrigger value="connections">{language === 'zh' ? '连接与管理' : 'Connections'}</TabsTrigger>
        </TabsList>
        <TabsContent value="general">
          <p className="px-4 pt-4 text-xs text-text-secondary">{language === 'zh' ? '外观和操作模式立即生效。任务预算和写入范围在任务计划中设置。' : 'Appearance and mode changes apply immediately. Set task budgets and write scope in the task plan.'}</p>
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

        </TabsContent>
        {canManage ? <TabsContent value="model" keepMounted>
          <p className="px-4 pt-4 text-xs text-text-secondary">{language === 'zh' ? '配置当前项目使用的模型。编辑后先保存，再测试连接。' : 'Configure the model for this project. Save changes before testing the connection.'}</p>
          <CopilotSettings hideActions onActionsReady={setCopilotActions} />
        </TabsContent> : null}
        <TabsContent value="connections">
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
          connected={backend.isPending ? null : backend.data?.status === 'ok'}
          detail={backend.data ? Object.entries(backend.data.checks ?? {}).map(([name, status]) => `${name}: ${status}`).join(' · ') || backend.data.service || backend.data.status : backend.error instanceof Error ? backend.error.message : t.settingsExt.connections.awaitingValidation}
        />
        {!guest ? <ConnectionRow
          label={t.settingsExt.connections.lsf}
          connected={cluster.isPending ? null : cluster.data?.connected === true}
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

        </TabsContent>
      </Tabs>
      </div>
    </DrawerShell>
  )
}

function ConnectionRow({ label, connected, configured = false, detail, successLabel }: { label: string; connected: boolean | null; configured?: boolean; detail: string; successLabel?: string }) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const isLongError = !connected && detail.length > 48

  return (
    <div className="rounded-xl border border-border-soft bg-bg-app px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <strong className="text-sm text-text-primary">{label}</strong>
        <StatusBadge
          status={connected === null ? 'neutral' : connected ? 'success' : configured ? 'info' : 'warning'}
          label={connected === null ? t.settingsExt.connections.awaitingValidation : connected ? successLabel ?? t.shared.status.connected : configured ? t.settingsExt.connections.configured : t.shared.status.disconnected}
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
