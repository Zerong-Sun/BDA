import { useEffect, useState } from 'react'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Frame, FrameFooter, FramePanel } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { Textarea } from '../../components/ui/textarea'
import { useI18n } from '../../lib/i18n'

export function DecisionReview({
  decisionId,
  roundNumber,
  patch,
  onSave,
  onReview,
  saving,
}: {
  decisionId: string
  roundNumber: number
  patch: unknown
  onSave: (id: string, patch: Record<string, unknown>) => Promise<unknown>
  onReview: (id: string, approve: boolean) => void
  saving: boolean
}) {
  const { t, format } = useI18n()
  const dr = t.research.campaign.decisionReview
  const initial = JSON.stringify(patch ?? { models: {} }, null, 2)
  const [draft, setDraft] = useState(initial)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const resetDraft = window.setTimeout(() => {
      const next = JSON.stringify(patch ?? { models: {} }, null, 2)
      setDraft(next)
      setDirty(false)
      setError('')
    }, 0)
    return () => window.clearTimeout(resetDraft)
  }, [decisionId, patch])

  const save = async () => {
    try {
      const parsed = JSON.parse(draft) as Record<string, unknown>
      await onSave(decisionId, parsed)
      setDirty(false)
      setError('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : dr.invalidParameterPatch)
    }
  }

  return (
    <Frame className="mt-3" spacing="sm">
      <FramePanel>
      <Textarea
        aria-label={format(dr.parameterPatchAriaLabel, { number: roundNumber })}
        className="min-h-28 font-mono"
        value={draft}
        onChange={(event) => {
          setDraft(event.target.value)
          setDirty(true)
          setError('')
        }}
      />
      {error ? <Alert className="mt-2" variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
      <FrameFooter className="mt-2 flex-row flex-wrap">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!dirty || saving}
          onClick={() => void save()}
        >
          {dr.savePatch}
        </Button>
        <Button
          type="button"
          size="sm"
          disabled={dirty || saving}
          onClick={() => onReview(decisionId, true)}
        >
          {dr.approveNextRound}
        </Button>
        <Button
          type="button"
          variant="destructive"
          size="sm"
          disabled={saving}
          onClick={() => onReview(decisionId, false)}
        >
          {dr.reject}
        </Button>
      </FrameFooter>
      </FramePanel>
    </Frame>
  )
}
