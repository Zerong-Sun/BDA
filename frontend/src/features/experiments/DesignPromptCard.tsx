import { useState } from 'react'
import { CaretDown, CaretUp, MagicWand } from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, AlertDescription } from '@/components/reui/alert'
import { Frame, FramePanel } from '@/components/reui/frame'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/textarea'
import { createProjectPromptDraft, updateProjectPrompt, waitForProjectPromptDraft } from '../../lib/api/projects'
import { useI18n } from '../../lib/i18n'
import type { Project } from '../../lib/schemas/project'

export function DesignPromptCard({ project }: { project: Project }) {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draftText, setDraftText] = useState('')

  const generate = useMutation({
    mutationFn: async () => {
      const { draft_id: draftId } = await createProjectPromptDraft({
        name: project.name,
        project_type: project.project_type,
        summary: project.summary ?? undefined,
      })
      return waitForProjectPromptDraft(draftId)
    },
    onSuccess: (draft) => {
      if (draft.status === 'ready' && draft.prompt) setDraftText(draft.prompt)
    },
  })

  const save = useMutation({
    mutationFn: () => updateProjectPrompt(project.id, draftText.trim(), project.version),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['project-overview', project.id] })
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
      await queryClient.invalidateQueries({ queryKey: ['project-library'] })
      setEditing(false)
      generate.reset()
    },
  })

  const startEditing = () => {
    setDraftText(project.prompt ?? '')
    generate.reset()
    save.reset()
    setEditing(true)
  }

  const cancelEditing = () => {
    setEditing(false)
    generate.reset()
    save.reset()
  }

  if (!project.prompt && !editing) {
    return (
      <Frame spacing="sm" className="mb-6">
        <FramePanel>
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-card-title font-semibold">{t.experimentsExt.overview.designPromptTitle}</h3>
            <Button type="button" variant="outline" size="sm" onClick={startEditing}>
              <MagicWand aria-hidden="true" />
              {t.experimentsExt.overview.designPromptCreate}
            </Button>
          </div>
        </FramePanel>
      </Frame>
    )
  }

  return (
    <Frame spacing="sm" className="mb-6">
      <FramePanel>
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-card-title font-semibold">{t.experimentsExt.overview.designPromptTitle}</h3>
          {editing ? null : (
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setExpanded((value) => !value)}>
                {expanded ? <CaretUp aria-hidden="true" /> : <CaretDown aria-hidden="true" />}
                {expanded ? t.experimentsExt.overview.designPromptHide : t.experimentsExt.overview.designPromptShow}
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={startEditing}>
                {t.experimentsExt.overview.designPromptEdit}
              </Button>
            </div>
          )}
        </div>

        {!editing && expanded ? (
          <p className="mt-3 whitespace-pre-wrap text-sm text-text-secondary">{project.prompt}</p>
        ) : null}

        {editing ? (
          <div className="mt-3 grid gap-2">
            <Textarea
              rows={6}
              value={draftText}
              onChange={(event) => setDraftText(event.target.value)}
              placeholder={t.projects.projectChooser.promptPlaceholder}
              aria-label={t.experimentsExt.overview.designPromptTitle}
            />
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" disabled={generate.isPending} onClick={() => generate.mutate()}>
                <MagicWand aria-hidden="true" />
                {generate.isPending
                  ? t.projects.projectChooser.generatingPrompt
                  : t.experimentsExt.overview.designPromptRegenerate}
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={!draftText.trim() || save.isPending}
                onClick={() => save.mutate()}
              >
                {t.experimentsExt.overview.designPromptSave}
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={cancelEditing}>
                {t.experimentsExt.overview.designPromptCancel}
              </Button>
            </div>
            {generate.isError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  {generate.error instanceof Error
                    ? generate.error.message
                    : t.projects.projectChooser.promptGenerateFailed}
                </AlertDescription>
              </Alert>
            ) : null}
            {save.isError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  {save.error instanceof Error ? save.error.message : t.experimentsExt.overview.designPromptSaveFailed}
                </AlertDescription>
              </Alert>
            ) : null}
          </div>
        ) : null}
      </FramePanel>
    </Frame>
  )
}
