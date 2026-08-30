import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CircleNotch, Flask, FolderPlus, MagicWand, Trash } from '@phosphor-icons/react'
import { Alert, AlertDescription } from '@/components/reui/alert'
import { IconTile } from '@/components/reui/icon-tile'
import { AppFrame } from '@/components/ui/AppFrame'
import { Button } from '@/components/ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { createProject, createProjectPromptDraft, waitForProjectPromptDraft } from '../../lib/api/projects'
import { useDeleteProjectLifecycle } from '../../lib/hooks/useDeleteProjectLifecycle'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useAppStore } from '../../lib/store/appStore'
import { useI18n } from '../../lib/i18n'
import { projectText } from '../../lib/i18n/projectText'

interface ProjectChooserProps {
  title?: string
  description?: string
  compact?: boolean
  creating?: boolean
  onCreatingChange?: (creating: boolean) => void
}

const PROJECT_TYPE_OPTIONS = [
  { value: 'protein_design', labelKey: 'proteinDesign' as const },
  { value: 'sweet_protein_design', labelKey: 'sweetProteinDesign' as const },
  { value: 'binder_design', labelKey: 'binderDesign' as const },
  { value: 'enzyme_design', labelKey: 'enzymeDesign' as const },
  { value: 'biomaterial_design', labelKey: 'biomaterialDesign' as const },
  { value: 'scaffold_redesign', labelKey: 'scaffoldRedesign' as const },
]

const NO_PROJECT_VALUE = '__no_project__'

export function ProjectChooser({
  title,
  description,
  compact = false,
  creating: creatingProp,
  onCreatingChange,
}: ProjectChooserProps) {
  const { t, format, language } = useI18n()
  const resolvedTitle = title ?? t.projects.projectChooser.defaultTitle
  const resolvedDescription = description ?? t.projects.projectChooser.defaultDescription
  const queryClient = useQueryClient()
  const { visibleProjects, projectId, setProjectId } = useProjectContext()
  const appMode = useAppStore((state) => state.appMode)
  const selectedProject = visibleProjects.find((project) => project.id === projectId) ?? null
  const projectDelete = useDeleteProjectLifecycle()
  const [creatingInternal, setCreatingInternal] = useState(false)
  const creating = creatingProp ?? creatingInternal
  const setCreating = (next: boolean) => {
    if (onCreatingChange) onCreatingChange(next)
    else setCreatingInternal(next)
  }
  const [name, setName] = useState('')
  const [projectType, setProjectType] = useState('protein_design')
  const [summary, setSummary] = useState('')
  const [prompt, setPrompt] = useState('')

  const generatePrompt = useMutation({
    mutationFn: async () => {
      const { draft_id: draftId } = await createProjectPromptDraft({
        name: name.trim(),
        project_type: projectType,
        summary: summary.trim() || undefined,
      })
      return waitForProjectPromptDraft(draftId)
    },
    onSuccess: (draft) => {
      if (draft.status === 'ready' && draft.prompt) setPrompt(draft.prompt)
    },
  })

  const create = useMutation({
    mutationFn: () =>
      createProject({
        name: name.trim(),
        project_type: projectType,
        summary: summary.trim() || undefined,
        prompt: prompt.trim(),
      }),
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
      setProjectId(project.id)
      setCreating(false)
      setName('')
      setSummary('')
      setPrompt('')
      generatePrompt.reset()
    },
  })

  const chooseProject = (nextProjectId: string | null) => {
    projectDelete.reset()
    setProjectId(nextProjectId === NO_PROJECT_VALUE ? '' : (nextProjectId ?? ''))
  }

  const confirmDelete = () => {
    if (selectedProject) projectDelete.confirmAndDeleteProject(selectedProject)
  }

  return (
    <>
      <AppFrame
        dense={compact}
        heading={
          <h2 className="flex items-center gap-2">
            <IconTile size="sm" variant="soft" className="text-accent">
              <Flask aria-hidden="true" />
            </IconTile>
            {resolvedTitle}
          </h2>
        }
        description={resolvedDescription}
        panelClassName={compact ? 'p-3' : 'p-5'}
      >
        <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
          <div className="grid gap-2">
            <Label htmlFor="project-chooser-trigger">{t.projects.projectChooser.existingProject}</Label>
            <Select value={projectId || NO_PROJECT_VALUE} onValueChange={chooseProject}>
              <SelectTrigger
                id="project-chooser-trigger"
                aria-label={t.projects.projectChooser.selectProjectAria}
                className="w-full"
              >
                <SelectValue placeholder={t.projects.projectChooser.selectPlaceholder} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_PROJECT_VALUE}>{t.projectLibrary.selectNone}</SelectItem>
                {visibleProjects.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {projectText(project, 'name', language)} · {project.status}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            type="button"
            variant="outline"
            className="self-end"
            disabled={appMode === 'demo'}
            onClick={() => setCreating(true)}
          >
            <FolderPlus aria-hidden="true" />
            {appMode === 'demo'
              ? t.projects.projectChooser.readOnlyDemo
              : t.projects.projectChooser.createProject}
          </Button>
        </div>

        {selectedProject ? (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <span className="min-w-0 truncate">
              {projectText(selectedProject, 'name', language)} · {selectedProject.id}
            </span>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              disabled={appMode === 'demo' || projectDelete.isPending}
              onClick={confirmDelete}
            >
              {projectDelete.isPending && projectDelete.deletingProjectId === selectedProject.id ? (
                <CircleNotch className="animate-spin" aria-hidden="true" />
              ) : (
                <Trash aria-hidden="true" />
              )}
              {t.projects.projectChooser.moveToTrash}
            </Button>
          </div>
        ) : null}
        {projectDelete.isSuccess ? (
          <Alert className="mt-3" variant="success">
            <AlertDescription>
              {format(t.projects.projectChooser.movedToTrash, {
                trashRoot: `${projectDelete.data.retention_days ?? 30} days`,
              })}
            </AlertDescription>
          </Alert>
        ) : null}
        {projectDelete.isError ? (
          <Alert className="mt-3" variant="destructive">
            <AlertDescription>
              {projectDelete.error instanceof Error
                ? projectDelete.error.message
                : t.projects.projectChooser.deleteFailed}
            </AlertDescription>
          </Alert>
        ) : null}
      </AppFrame>

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t.projects.projectChooser.createProject}</DialogTitle>
            <DialogDescription>{resolvedDescription}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="project-name">{t.projects.projectChooser.projectName}</Label>
              <Input
                id="project-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={t.projects.projectChooser.projectNamePlaceholder}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="project-type-trigger">{t.projects.projectChooser.projectType}</Label>
              <Select value={projectType} onValueChange={(value) => setProjectType(value ?? 'protein_design')}>
                <SelectTrigger id="project-type-trigger" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROJECT_TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {t.projects.types[option.labelKey]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="project-objective">
                {t.projects.projectChooser.objectiveConstraints}
              </Label>
              <Textarea
                id="project-objective"
                rows={3}
                value={summary}
                onChange={(event) => setSummary(event.target.value)}
                placeholder={t.projects.projectChooser.objectivePlaceholder}
              />
            </div>
            <div className="grid gap-2">
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor="project-prompt">{t.projects.projectChooser.promptLabel}</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!name.trim() || generatePrompt.isPending}
                  onClick={() => generatePrompt.mutate()}
                >
                  {generatePrompt.isPending ? (
                    <CircleNotch className="animate-spin" aria-hidden="true" />
                  ) : (
                    <MagicWand aria-hidden="true" />
                  )}
                  {generatePrompt.isPending
                    ? t.projects.projectChooser.generatingPrompt
                    : t.projects.projectChooser.generatePrompt}
                </Button>
              </div>
              <Textarea
                id="project-prompt"
                rows={6}
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder={t.projects.projectChooser.promptPlaceholder}
              />
              <p className="text-xs text-muted-foreground">{t.projects.projectChooser.promptRequiredHint}</p>
            </div>
            {generatePrompt.isError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  {generatePrompt.error instanceof Error
                    ? generatePrompt.error.message
                    : t.projects.projectChooser.promptGenerateFailed}
                </AlertDescription>
              </Alert>
            ) : null}
            {create.isError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  {create.error instanceof Error
                    ? create.error.message
                    : t.projects.projectChooser.createFailed}
                </AlertDescription>
              </Alert>
            ) : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCreating(false)}>
              {language === 'zh' ? '取消' : 'Cancel'}
            </Button>
            <Button
              type="button"
              disabled={!name.trim() || !prompt.trim() || create.isPending}
              onClick={() => create.mutate()}
              aria-busy={create.isPending}
            >
              {create.isPending ? <CircleNotch className="animate-spin" aria-hidden="true" /> : <FolderPlus aria-hidden="true" />}
              {t.projects.projectChooser.createAndSelect}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
