import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { ArrowUpRight, Books, Cube, Quotes, Plus, CircleNotch, MagnifyingGlass, Trash } from '@phosphor-icons/react'
import { Alert, AlertAction, AlertDescription } from '@/components/reui/alert'
import { Disclosure } from '../../components/ui/Disclosure'
import { AppFrame } from '@/components/ui/AppFrame'
import { ApiState } from '../../components/ui/ApiState'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Skeleton } from '@/components/ui/Skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { StatusPills } from '../../components/ui/StatusPill'
import { useI18n } from '../../lib/i18n'
import { projectText } from '../../lib/i18n/projectText'
import type { Project } from '../../lib/api/projects'
import { listProjectLibrary } from '../../lib/api/projects'
import { getBundledProteinResearchPackage, syncBundledProteinResearchPackage } from '../../lib/api/researchPackages'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import type { useDeleteProjectLifecycle } from '../../lib/hooks/useDeleteProjectLifecycle'
import { currentRole } from '../research/jsonHelpers'
import { projectBrief } from '../projects/projectBrief'

type SortKey = 'status' | 'name' | 'recent'

interface ProjectLibraryProps {
  onCreate: () => void
  onToggleIntro: () => void
  introOpen: boolean
  onManage: (project: Project) => void
  projectDelete: ReturnType<typeof useDeleteProjectLifecycle>
}

function statusPriority(project: Project) {
  if (project.status === 'running') return 0
  if (project.status === 'active') return 1
  return 2
}

function formatProjectType(projectType: string) {
  return projectType.replace(/_/g, ' ')
}

function ProjectLibrarySkeleton() {
  const { t } = useI18n()
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label={t.projectLibrary.loading}>
      {Array.from({ length: 3 }).map((_, index) => (
        <AppFrame key={index} panelClassName="grid gap-3 p-4">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-6 w-3/4" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-8 w-40" />
        </AppFrame>
      ))}
    </div>
  )
}

export function ProjectLibrary({ onCreate, onToggleIntro, introOpen, onManage, projectDelete }: ProjectLibraryProps) {
  const { t, language, format } = useI18n()
  const client = useQueryClient()
  const {
    visibleProjects,
    projectId,
    projectsLoading,
    projectsError,
    projectsQueryError,
    refetchProjects,
  } = useProjectContext()
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sortKey, setSortKey] = useState<SortKey>('recent')
  const role = currentRole()
  const librarySummary = useQuery({
    queryKey: ['project-library'],
    queryFn: listProjectLibrary,
    refetchInterval: (queryState) => queryState.state.data?.some(
      (item) => item.source_project_key && item.structure_count > 0 && !item.primary_structure_ready,
    ) ? 10_000 : false,
  })
  const bundleVersion = useQuery({
    queryKey: ['bundled-research-package-version'],
    queryFn: getBundledProteinResearchPackage,
    staleTime: Infinity,
    select: (bundle) => ({ packageId: bundle.package_id, version: bundle.version }),
  })
  const summaryByProject = useMemo(
    () => new Map((librarySummary.data ?? []).map((item) => [item.id, item])),
    [librarySummary.data],
  )
  const packageSync = useMutation({
    mutationFn: syncBundledProteinResearchPackage,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['projects'] })
      client.invalidateQueries({ queryKey: ['project-library'] })
      client.invalidateQueries({ queryKey: ['research-workspace'] })
    },
  })

  useEffect(() => {
    if (import.meta.env.MODE === 'test' || projectsLoading || projectsError) return
    if (!['admin', 'researcher'].includes(role)) return
    const marker = 'bda-research-package-sync-attempted'
    if (sessionStorage.getItem(marker)) return
    sessionStorage.setItem(marker, 'true')
    packageSync.mutate()
  }, [packageSync, projectsError, projectsLoading, role])

  const viewerPackageOutdated = role === 'viewer' && Boolean(bundleVersion.data) && visibleProjects.some((project) => {
    if (project.source_package_id !== bundleVersion.data?.packageId) return false
    const packageInfo = project.localized_content?.package
    return Boolean(packageInfo && typeof packageInfo === 'object'
      && (packageInfo as Record<string, unknown>).version !== bundleVersion.data?.version)
  })

  const localizedProjectText = useCallback(
    (project: Project, key: 'name' | 'summary') => projectText(project, key, language),
    [language],
  )

  const filteredProjects = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    let items = visibleProjects.filter((project) => {
      if (statusFilter !== 'all' && project.status !== statusFilter) return false
      if (!normalized) return true
      return (
        localizedProjectText(project, 'name').toLowerCase().includes(normalized) ||
        project.id.toLowerCase().includes(normalized) ||
        localizedProjectText(project, 'summary').toLowerCase().includes(normalized) ||
        projectBrief(project, language).objective.toLowerCase().includes(normalized)
      )
    })

    items = [...items].sort((a, b) => {
      if (sortKey === 'name') return localizedProjectText(a, 'name').localeCompare(localizedProjectText(b, 'name'), language)
      if (sortKey === 'recent') {
        const aTime = a.updated_at ?? a.created_at ?? ''
        const bTime = b.updated_at ?? b.created_at ?? ''
        if (aTime && bTime) return bTime.localeCompare(aTime)
        return b.id.localeCompare(a.id)
      }
      return statusPriority(a) - statusPriority(b) || localizedProjectText(a, 'name').localeCompare(localizedProjectText(b, 'name'), language)
    })

    return items
  }, [language, localizedProjectText, query, sortKey, statusFilter, visibleProjects])

  const statusOptions = useMemo(() => {
    const statuses = new Set(visibleProjects.map((project) => project.status))
    return ['all', ...Array.from(statuses).sort()]
  }, [visibleProjects])

  return (
    <section className="project-library mb-6">
      <div className="project-library-heading">
        <div>
          <h2>{t.projectLibrary.title}<span className="project-library-count">{visibleProjects.length}</span></h2>
          <p className="mt-1 text-sm text-text-secondary">{t.projectLibrary.subtitle}</p>
        </div>
        <div className="project-library-actions"><Button type="button" variant="ghost" onClick={onToggleIntro} aria-expanded={introOpen}>{t.experimentsExt.gettingStarted}</Button>
        <Button type="button" className="science-primary" onClick={onCreate}>
          <Plus aria-hidden="true" />{t.common.newExperiment}
        </Button></div>
      </div>

      <div className="project-library-filters">
        <label className="relative min-w-[12rem] flex-1">
          <MagnifyingGlass className="pointer-events-none absolute left-2.5 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <Input
            aria-label={t.projectLibrary.searchPlaceholder}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t.projectLibrary.searchPlaceholder}
            className="w-full pl-8"
          />
        </label>
        <Select items={statusOptions.map((status) => ({ value: status, label: status === 'all' ? t.projectLibrary.filterAll : status }))} value={statusFilter} onValueChange={(value) => setStatusFilter(value ?? 'all')}>
          <SelectTrigger aria-label={t.projectLibrary.filterStatus}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {statusOptions.map((status) => (
              <SelectItem key={status} value={status}>
                {status === 'all' ? t.projectLibrary.filterAll : status}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select items={[{ value: 'recent', label: t.projectLibrary.sortRecent }, { value: 'status', label: t.projectLibrary.sortStatus }, { value: 'name', label: t.projectLibrary.sortName }]} value={sortKey} onValueChange={(value) => setSortKey((value ?? 'recent') as SortKey)}>
          <SelectTrigger aria-label={t.projectLibrary.sortBy}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="recent">{t.projectLibrary.sortRecent}</SelectItem>
            <SelectItem value="status">{t.projectLibrary.sortStatus}</SelectItem>
            <SelectItem value="name">{t.projectLibrary.sortName}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <ApiState
        isLoading={projectsLoading}
        isError={projectsError}
        error={projectsQueryError}
        onRetry={() => void refetchProjects()}
        loadingSkeleton={<ProjectLibrarySkeleton />}
      >
        {packageSync.isPending ? (
          <Alert className="mb-4" variant="info">
            <AlertDescription>{t.projectLibrary.builtinSyncing}</AlertDescription>
          </Alert>
        ) : null}
        {packageSync.isError ? (
          <Alert className="mb-4" variant="destructive">
            <AlertDescription>{t.projectLibrary.syncFailed}</AlertDescription>
            <AlertAction>
              <Button type="button" size="sm" variant="outline" onClick={() => packageSync.mutate()}>{t.shared.apiState.retry}</Button>
            </AlertAction>
          </Alert>
        ) : null}
        {viewerPackageOutdated ? (
          <Alert className="mb-4" variant="warning">
            <AlertDescription>{t.projectLibrary.packageUpdateAvailable}</AlertDescription>
          </Alert>
        ) : null}
        {visibleProjects.length === 0 ? (
          <AppFrame className="border-dashed" panelClassName="p-6 text-sm text-text-secondary">
            <h3 className="text-lg font-semibold text-text-primary">{t.projectLibrary.empty}</h3>
            <p className="mt-2 max-w-2xl">{t.projectLibrary.emptyBody}</p>
            <Button type="button" className="mt-4" onClick={onCreate}>
              {t.projectLibrary.createFirst}
            </Button>
          </AppFrame>
        ) : filteredProjects.length === 0 ? (
          <AppFrame className="border-dashed" panelClassName="p-6 text-sm text-text-secondary">
            <p>{t.projectLibrary.noResults}</p>
            <Button type="button" variant="ghost" size="sm" className="mt-3" onClick={() => { setQuery(''); setStatusFilter('all') }}>
              {t.projectLibrary.clearSearch}
            </Button>
          </AppFrame>
        ) : (
          <div className="project-list">
            {filteredProjects.map((project, index) => {
              const isActive = project.id === projectId
              const isDeleting = projectDelete.deletingProjectId === project.id
              const summary = summaryByProject.get(project.id)
              const brief = projectBrief(project, language)
              const query = `?project=${encodeURIComponent(project.id)}`
              return <article key={project.id} className="project-row" data-active={isActive || undefined}>
                <span className="project-index">{String(index + 1).padStart(2, '0')}</span>
                <div className="project-row-body">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="science-eyebrow">{formatProjectType(project.project_type)}</span>
                    <StatusPills status={project.status} />
                    {brief.source === 'public-package' ? <span className="project-source">{language === 'zh' ? '公开演示' : 'Public demo'}</span> : null}
                  </div>
                  <h3><Link to={`/research${query}&tab=goals`}>{localizedProjectText(project, 'name')}</Link></h3>
                  <p className="project-row-objective">{brief.objective || (language === 'zh' ? '尚未定义目标，打开项目补充。' : 'Define the objective in the project brief.')}</p>
                  <div className="project-facts">
                    {summary ? <>
                      <Link to={`/research${query}&tab=references`}><Books aria-hidden="true" />{format(t.projectLibrary.referencesCount, { count: summary.reference_count })}</Link>
                      <Link to={`/research${query}&tab=structures`}><Cube aria-hidden="true" />{format(t.projectLibrary.pdbCount, { count: summary.structure_count })}</Link>
                      <Link to={`/research${query}&tab=evidence`}><Quotes aria-hidden="true" />{format(t.projectLibrary.claimsCount, { count: summary.finding_count })}</Link>
                    </> : <span>{language === 'zh' ? '资料统计待加载' : 'Material counts unavailable'}</span>}
                    <span>{language === 'zh' ? '更新于 ' : 'Updated '}{new Date(project.updated_at || project.created_at).toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US')}</span>
                  </div>
                </div>
                <div className="project-row-actions">
                  <Button type="button" render={<Link to={`/research${query}&tab=goals`} />}>{t.projectLibrary.open}<ArrowUpRight aria-hidden="true" /></Button>
                  <Button type="button" variant="outline" render={<Link to={`/bots${query}`} />}>{language === 'zh' ? '研究团队' : 'Research team'}</Button>
                  <Disclosure className="project-row-menu" title={language === 'zh' ? '更多操作' : 'More actions'}><div>
                    <Button type="button" variant="ghost" size="sm" onClick={() => onManage(project)}>{t.projectLibrary.manage}</Button>
                    <Button type="button" variant="ghost" size="sm" disabled={isDeleting || projectDelete.isPending} onClick={() => projectDelete.confirmAndDeleteProject(project)}>
                      {isDeleting ? <CircleNotch className="h-4 w-4 animate-spin" /> : <Trash className="h-4 w-4" />}{t.projectLibrary.moveToTrash}
                    </Button>
                  </div></Disclosure>
                </div>
              </article>
            })}
          </div>
        )}
      </ApiState>
    </section>
  )
}
