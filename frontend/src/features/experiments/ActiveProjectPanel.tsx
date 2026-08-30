import { useState } from 'react'
import { Link } from 'react-router'
import { FolderPlus } from '@phosphor-icons/react'
import { Alert, AlertDescription } from '@/components/reui/alert'
import { AppFrame } from '@/components/ui/AppFrame'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/Skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { StatusPills } from '../../components/ui/StatusPill'
import type { Project } from '../../lib/api/projects'
import { useI18n } from '../../lib/i18n'
import { projectText } from '../../lib/i18n/projectText'
import {
  useProjectTargetStructure,
  useTargetReadiness,
} from '../../lib/hooks/useProjectTargetStructure'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { approveTargetStructure, prepareTargetStructure } from '../../lib/api/projects'
import { ProjectTargetViewer } from '../pdb-viewer/ProjectTargetViewer'
import { PDBFileUpload } from '../pdb-viewer/PDBFileUpload'
import { StructureViewerLazy } from '../pdb-viewer/StructureViewerLazy'
import { structureSourceFromUrl } from '../pdb-viewer/types'
import { TargetStructureOverlay } from './TargetStructureOverlay'

interface ActiveProjectPanelProps {
  project: Project | null
  projectQuery: string
  readOnly?: boolean
  onManage: () => void
  onCreate: () => void
}

export function ActiveProjectPanel({
  project,
  projectQuery,
  readOnly = false,
  onManage,
  onCreate,
}: ActiveProjectPanelProps) {
  const { t, language } = useI18n()
  const targetQuery = useProjectTargetStructure(project?.id)
  const readinessQuery = useTargetReadiness(project?.id)
  const queryClient = useQueryClient()
  const [previewFile, setPreviewFile] = useState<File | null>(null)
  const [chainSelection, setChainSelection] = useState('')
  const prepareStructure = useMutation({
    mutationFn: async () => {
      if (readOnly) throw new Error(t.projects.activeProjectPanel.readOnly)
      return prepareTargetStructure(project!.id, {
        selected_chains: chainSelection
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        remove_waters: true,
        remove_heteroatoms: false,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['target-readiness', project?.id] })
      queryClient.invalidateQueries({ queryKey: ['project-target-structure', project?.id] })
      queryClient.invalidateQueries({ queryKey: ['project-overview', project?.id] })
    },
  })
  const approveStructure = useMutation({
    mutationFn: async (revisionId: string) => {
      if (readOnly) throw new Error(t.projects.activeProjectPanel.readOnly)
      return approveTargetStructure(project!.id, revisionId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['target-readiness', project?.id] })
      queryClient.invalidateQueries({ queryKey: ['project-target-structure', project?.id] })
      queryClient.invalidateQueries({ queryKey: ['project-overview', project?.id] })
    },
  })

  if (!project) {
    return (
      <AppFrame
        className="mb-6"
        heading={<h2>{t.projects.activeProjectPanel.noProject}</h2>}
        description={t.projects.activeProjectPanel.noProjectBody}
        panelClassName="p-5"
      >
        <Button type="button" className="mt-4" onClick={onCreate}>
          <FolderPlus className="h-4 w-4" />
          {t.projects.activeProjectPanel.newProject}
        </Button>
      </AppFrame>
    )
  }

  return (
    <AppFrame
      className="mb-6"
      heading={
        <h2 className="line-clamp-2" title={projectText(project, 'name', language)}>
          {projectText(project, 'name', language)}
        </h2>
      }
      description={t.projects.activeProjectPanel.activeProject}
      actions={<StatusPills status={project.status} />}
      panelClassName="p-5"
    >
      <div className="flex flex-wrap gap-2">
        <Button
          render={<Link to={
            readinessQuery.data?.ready_for_workflow
              ? `/workflow${projectQuery}`
              : `/research?tab=structures&project=${encodeURIComponent(project.id)}`
          } />}
        >
          {readinessQuery.data?.ready_for_workflow
            ? t.projects.activeProjectPanel.continueWorkflow
            : t.projects.activeProjectPanel.resolveTarget}
        </Button>
        <Button type="button" variant="outline" onClick={onManage}>
          {t.projects.activeProjectPanel.manageProject}
        </Button>
      </div>
      <div className="mt-4 rounded-xl border border-border-soft bg-surface-1 p-4">
        <h3 className="text-sm font-semibold text-text-primary">
          {t.projects.activeProjectPanel.targetStructureTitle}
        </h3>
        {readinessQuery.data ? (
          <Alert className="mt-3" variant={readinessQuery.data.ready_for_workflow ? 'success' : 'warning'}>
            <AlertDescription>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <strong>
                {readinessQuery.data.ready_for_workflow
                  ? t.projects.activeProjectPanel.targetReady
                  : t.projects.activeProjectPanel.targetBlocked}
              </strong>
              <span>{readinessQuery.data.next_action}</span>
            </div>
            {readinessQuery.data.blockers.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-4">
                {readinessQuery.data.blockers.map((blocker) => (
                  <li key={blocker}>{blocker}</li>
                ))}
              </ul>
            ) : null}
            </AlertDescription>
          </Alert>
        ) : null}
        {targetQuery.isLoading ? (
          <div className="mt-3 grid gap-2" aria-label={t.projectLibrary.targetStructureLoading}>
            <Skeleton className="h-72 w-full" />
            <Skeleton className="h-4 w-52" />
          </div>
        ) : targetQuery.data ? (
          <div className="mt-3">
            <ProjectTargetViewer target={targetQuery.data} height={320} />
            <TargetStructureOverlay
              target={targetQuery.data}
              readiness={readinessQuery.data}
              projectId={project.id}
            />
          </div>
        ) : (
          <div className="mt-3">
            {previewFile ? (
              <StructureViewerLazy
                source={structureSourceFromUrl(null, { file: previewFile })}
                height={320}
                showMetadata={false}
              />
            ) : null}
            <p className="mt-3 text-sm text-text-secondary">
              {t.projects.activeProjectPanel.targetStructureEmpty}
            </p>
            {project ? (
              <PDBFileUpload
                projectId={project.id}
                selectedFile={previewFile}
                readOnly={readOnly}
                onFileSelected={setPreviewFile}
                onUploaded={() => {
                  setPreviewFile(null)
                  queryClient.invalidateQueries({
                    queryKey: ['project-target-structure', project.id],
                  })
                  queryClient.invalidateQueries({
                    queryKey: ['target-readiness', project.id],
                  })
                }}
              />
            ) : null}
          </div>
        )}
        {targetQuery.data ? (
          <div className="mt-4 rounded-lg border border-border-soft bg-bg-app p-3">
            <div className="grid gap-2">
              <Label htmlFor="target-chain-selection">{t.projects.activeProjectPanel.chainsLabel}</Label>
              <Input
                id="target-chain-selection"
                value={chainSelection}
                disabled={readOnly}
                onChange={(event) => setChainSelection(event.target.value)}
                placeholder={(Array.isArray(targetQuery.data.artifact?.lineage.chains)
                  ? targetQuery.data.artifact.lineage.chains.filter((item): item is string => typeof item === 'string').join(',')
                  : '') || 'A'}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button type="button"
                variant="outline"
                size="sm"
                disabled={readOnly || prepareStructure.isPending || approveStructure.isPending}
                onClick={() => prepareStructure.mutate()}
              >
                {t.projects.activeProjectPanel.prepareStructure}
              </Button>
              {targetQuery.data.structure.latest_revision?.status === 'prepared' ? (
                <Button type="button"
                  size="sm"
                  disabled={readOnly || approveStructure.isPending || prepareStructure.isPending}
                  onClick={() =>
                    approveStructure.mutate(
                      targetQuery.data!.structure.latest_revision!.id,
                    )
                  }
                >
                  {t.projects.activeProjectPanel.approveStructure}
                </Button>
              ) : null}
            </div>
            {prepareStructure.isError ? (
              <Alert className="mt-2" variant="destructive">
                <AlertDescription>{prepareStructure.error.message}</AlertDescription>
              </Alert>
            ) : null}
            {approveStructure.isError ? (
              <Alert className="mt-2" variant="destructive">
                <AlertDescription>{approveStructure.error.message}</AlertDescription>
              </Alert>
            ) : null}
            {targetQuery.data.structure.latest_revision?.options ? (
              <ScrollArea className="mt-3 h-48 rounded border border-border-soft">
                <pre className="whitespace-pre-wrap p-2 text-[11px] text-text-secondary">
                  {JSON.stringify(
                    targetQuery.data.structure.latest_revision.options,
                    null,
                    2,
                  )}
                </pre>
              </ScrollArea>
            ) : null}
          </div>
        ) : null}
      </div>
    </AppFrame>
  )
}
