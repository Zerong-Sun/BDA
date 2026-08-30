import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BookOpenTextIcon, SpinnerGapIcon } from '@phosphor-icons/react'
import { upsertProjectResearchFinding } from '../../lib/api/projects'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Button } from '../../components/ui/Button'
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from '../../components/ui/popover'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import { parseReviewFinding } from './parseReviewFinding'
import {
  inferTrackFromText,
  isReviewTrack,
  REVIEW_SECTION_ORDER,
  reviewSectionLabel,
  type ReviewTrack,
} from './reviewTracks'

interface SaveToReviewButtonProps {
  projectId: string
  content: string
  reviewTrack?: string
  reviewIntent?: boolean
  userPrompt?: string
  onResearchPage?: boolean
  citations?: Array<Record<string, unknown>>
}

export function SaveToReviewButton({
  projectId,
  content,
  reviewTrack,
  reviewIntent,
  userPrompt,
  onResearchPage,
  citations,
}: SaveToReviewButtonProps) {
  const { t, language } = useI18n()
  const r = t.research.projectReview
  const queryClient = useQueryClient()
  const showToast = useToastStore((s) => s.show)
  const [pickerOpen, setPickerOpen] = useState(false)
  const inferredTrack =
    (reviewTrack && isReviewTrack(reviewTrack) ? reviewTrack : undefined) ??
    (userPrompt ? inferTrackFromText(userPrompt, language) : undefined)
  const [selectedTrack, setSelectedTrack] = useState<ReviewTrack>(inferredTrack ?? REVIEW_SECTION_ORDER[0])

  const save = useMutation({
    mutationFn: (track: string) => {
      const payload = parseReviewFinding(content, track)
      const existingEvidence = payload.evidence ?? {}
      payload.evidence = {
        ...existingEvidence,
        citations: citations ?? [],
        source_refs: citations?.flatMap((citation) => {
          const refs = Array.isArray(citation.reference_ids) ? citation.reference_ids.map(String) : []
          const url = typeof citation.url === 'string' && citation.url ? [citation.url] : []
          return [...refs, ...url]
        }) ?? existingEvidence.source_refs,
        source_language: language,
        localized_content: {
          title: { [language]: payload.title },
          content: { [language]: payload.content },
        },
      }
      return upsertProjectResearchFinding(projectId, payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-research-summary', projectId] })
      queryClient.invalidateQueries({ queryKey: ['research-workspace', projectId] })
      showToast(r.savedToReview, 'success')
      setPickerOpen(false)
    },
  })

  const canShow = Boolean(
    projectId &&
      content.trim() &&
      (reviewTrack || reviewIntent || onResearchPage),
  )
  if (!canShow) return null

  return (
    <div className="mt-2 border-t border-border-soft pt-2">
      {inferredTrack ? (
        <Button
          type="button"
          variant="outline"
          size="xs"
          disabled={save.isPending}
          onClick={() => save.mutate(inferredTrack)}
        >
          {save.isPending ? (
            <SpinnerGapIcon className="animate-spin" aria-hidden="true" />
          ) : (
            <BookOpenTextIcon aria-hidden="true" />
          )}
          {r.saveToReview}
        </Button>
      ) : (
        <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
          <PopoverTrigger render={<Button type="button" variant="outline" size="xs" disabled={save.isPending} />}>
            <BookOpenTextIcon aria-hidden="true" />
            {r.saveToReview}
          </PopoverTrigger>
          <PopoverContent align="start">
            <PopoverHeader>
              <PopoverTitle>{r.pickSection}</PopoverTitle>
              <PopoverDescription>{r.usageAdd}</PopoverDescription>
            </PopoverHeader>
            <div className="flex flex-wrap gap-1">
              {REVIEW_SECTION_ORDER.map((track) => (
                <Button
                  key={track}
                  type="button"
                  variant={selectedTrack === track ? 'secondary' : 'outline'}
                  size="xs"
                  aria-pressed={selectedTrack === track}
                  onClick={() => setSelectedTrack(track)}
                >
                  {reviewSectionLabel(track, language)}
                </Button>
              ))}
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                size="xs"
                disabled={save.isPending}
                onClick={() => save.mutate(selectedTrack)}
              >
                {save.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : null}
                {r.saveToReview}
              </Button>
              <Button type="button" variant="outline" size="xs" onClick={() => setPickerOpen(false)}>
                {r.close}
              </Button>
            </div>
          </PopoverContent>
        </Popover>
      )}
      {save.isError ? (
        <Alert className="mt-2" variant="destructive">
          <AlertDescription>{r.saveToReviewFailed}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}
