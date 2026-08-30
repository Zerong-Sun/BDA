import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { CircleNotch, MagnifyingGlass, Trash } from '@phosphor-icons/react'
import { Alert, AlertAction, AlertDescription } from '@/components/reui/alert'
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
import { RepresentativeStructurePreview } from './RepresentativeStructurePreview'

type SortKey = 'status' | 'name' | 'recent'

interface ProjectLibraryProps {
  onCreate: () => void
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

function ProjectCardStructurePreview({ project }: { project: Project }) {
  return <RepresentativeStructurePreview project={project} />
}

export function ProjectLibrary({ onCreate, onManage, projectDelete }: ProjectLibraryProps) {
  const { t, language, format } = useI18n()
  const navigate = useNavigate()
  const client = useQueryClient()
  const {
    visibleProjects,
    projectId,
    setProjectId,
    projectsLoading,
    projectsError,
    projectsQueryError,
    refetchProjects,
  } = useProjectContext()
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sortKey, setSortKey] = useState<SortKey>('recent')
  const [expandedPrompts, setExpandedPrompts] = useState<Set<string>>(new Set())
  const togglePromptExpanded = (projectId: string) => {
    setExpandedPrompts((current) => {
      const next = new Set(current)
      if (next.has(projectId)) next.delete(projectId)
      else next.add(projectId)
      return next
    })
  }
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
        (project.summary ?? '').toLowerCase().includes(normalized)
      )
    })

    items = [...items].sort((a, b) => {
      if (sortKey === 'name') return a.name.localeCompare(b.name)
      if (sortKey === 'recent') {
        const aTime = a.created_at ?? ''
        const bTime = b.created_at ?? ''
        if (aTime && bTime) return bTime.localeCompare(aTime)
        return b.id.localeCompare(a.id)
      }
      return statusPriority(a) - statusPriority(b) || a.name.localeCompare(b.name)
    })

    return items
  }, [localizedProjectText, query, sortKey, statusFilter, visibleProjects])

  const statusOptions = useMemo(() => {
    const statuses = new Set(visibleProjects.map((project) => project.status))
    return ['all', ...Array.from(statuses).sort()]
  }, [visibleProjects])

  return (
    <section className="mb-6">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-card-title font-semibold">{t.projectLibrary.title}</h2>
          <p className="mt-1 text-sm text-text-secondary">{t.projectLibrary.subtitle}</p>
        </div>
        <Button type="button" onClick={onCreate}>
          {t.common.newExperiment}
        </Button>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <label className="relative min-w-[12rem] flex-1">
          <MagnifyingGlass className="pointer-events-none absolute left-2.5 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <Input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t.projectLibrary.searchPlaceholder}
            className="w-full pl-8"
          />
        </label>
        <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value ?? 'all')}>
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
        <Select value={sortKey} onValueChange={(value) => setSortKey((value ?? 'recent') as SortKey)}>
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
            <Button type="button" variant="ghost" size="sm" className="mt-3" onClick={() => setQuery('')}>
              {t.projectLibrary.clearSearch}
            </Button>
          </AppFrame>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredProjects.map((project) => {
              const isActive = project.id === projectId
              const isDeleting = projectDelete.deletingProjectId === project.id
              const summary = summaryByProject.get(project.id)
              return (
                <AppFrame
                  key={project.id}
                  className={isActive ? 'ring-1 ring-accent/40' : undefined}
                  panelClassName="p-0"
                >
                  <div className="space-y-3 p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs uppercase tracking-wide text-text-muted">
                          {formatProjectType(project.project_type)}
                        </p>
                        <h3 className="mt-1 line-clamp-2 font-semibold text-text-primary" title={localizedProjectText(project, 'name')}>
                          {localizedProjectText(project, 'name')}
                        </h3>
                      </div>
                      <StatusPills status={project.status} />
                    </div>
                    {localizedProjectText(project, 'summary') ? (
                      <p className="line-clamp-2 text-xs text-text-secondary">{localizedProjectText(project, 'summary')}</p>
                    ) : null}
                    {project.prompt ? (
                      <div className="text-xs text-text-secondary">
                        <p className="font-medium text-text-primary">{t.projectLibrary.promptLabel}</p>
                        <p className={expandedPrompts.has(project.id) ? 'mt-1 whitespace-pre-wrap' : 'mt-1 line-clamp-2'}>
                          {project.prompt}
                        </p>
                        <Button
                          type="button"
                          variant="link"
                          size="xs"
                          className="mt-1 h-auto p-0 text-text-muted"
                          onClick={() => togglePromptExpanded(project.id)}
                        >
                          {expandedPrompts.has(project.id) ? t.projectLibrary.promptShowLess : t.projectLibrary.promptShowMore}
                        </Button>
                      </div>
                    ) : null}
                    <ProjectCardStructurePreview project={project} />
                    {summary ? (
                      <div className="flex flex-wrap gap-1.5 text-[10px] text-text-secondary">
                        {summary.research_candidate_count ? <span className="rounded border border-border-soft px-2 py-1">{format(t.projectLibrary.researchTargetsCount, { count: summary.research_candidate_count })}</span> : null}
                        <span className="rounded border border-border-soft px-2 py-1">{format(t.projectLibrary.pdbCount, { count: summary.structure_count })}</span>
                        <span className="rounded border border-border-soft px-2 py-1">{format(t.projectLibrary.referencesCount, { count: summary.reference_count })}</span>
                        <span className="rounded border border-border-soft px-2 py-1">{format(t.projectLibrary.claimsCount, { count: summary.finding_count })}</span>
                      </div>
                    ) : null}
                    <p className="text-[11px] text-text-muted">
                      {project.created_at ? new Date(project.created_at).toLocaleDateString() : project.id}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button type="button"
                        variant={isActive ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setProjectId(project.id)}
                      >
                        {isActive ? t.projectLibrary.current : t.projectLibrary.open}
                      </Button>
                      <Button type="button" variant="ghost" size="sm" onClick={() => onManage(project)}>
                        {t.projectLibrary.manage}
                      </Button>
                      {project.source_project_key ? (
                        <Button type="button" variant="ghost" size="sm" onClick={() => { setProjectId(project.id); navigate(`/research?project=${encodeURIComponent(project.id)}&tab=evidence`) }}>
                          {t.projectLibrary.researchAction}
                        </Button>
                      ) : null}
                      {summary?.structure_count ? (
                        <Button type="button" variant="ghost" size="sm" onClick={() => { setProjectId(project.id); navigate(`/research?project=${encodeURIComponent(project.id)}&tab=structures`) }}>
                          {t.projectLibrary.allStructures}
                        </Button>
                      ) : null}
                      <Button type="button"
                        variant="ghost"
                        size="sm"
                        disabled={isDeleting || projectDelete.isPending}
                        onClick={() => projectDelete.confirmAndDeleteProject(project)}
                      >
                        {isDeleting ? (
                          <CircleNotch className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash className="h-4 w-4" />
                        )}
                        {t.projectLibrary.moveToTrash}
                      </Button>
                    </div>
                  </div>
                </AppFrame>
              )
            })}
          </div>
        )}
      </ApiState>
    </section>
  )
}
