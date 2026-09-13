import { ArrowRightIcon, WarningCircleIcon } from '@phosphor-icons/react'
import type { HandoffResponse } from '../../lib/api/generated'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Frame, FramePanel } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { useCopilotBots, type CopilotBot } from './bots/registry'
import { useCopilotHandoffs } from './handoffs'

/**
 * The record of what one operator handed the next, and what it claimed.
 *
 * This surface exists because the record had none. `copilot_handoffs` is what
 * makes the roster auditable - a claim carries the evidence reference behind it,
 * so "claim 3 cites nothing" is a lookup rather than an opinion - and until now
 * the only way to see any of it was to ask the Copilot to read its own inbox in
 * chat. A record only the operators can read is not a record; it is the last
 * operator's account of itself.
 *
 * So the unsupported claim is the thing this view is built around. It is not an
 * error and it is not hidden: the operator made it, the platform wrote it down
 * as unsupported rather than dropping it, and a reader looking for what to check
 * should find it first.
 */

/** What a claim's confidence says about its evidence, not about how sure the bot sounds. */
const CONFIDENCE_VARIANT: Record<string, 'destructive' | 'warning' | 'success'> = {
  unsupported: 'destructive',
  consistent: 'warning',
  stated: 'success',
}

/** The label for a confidence level, falling back to the raw value.
 *
 * A level this build does not know is shown rather than blanked: the record was
 * written by a server that may be newer, and hiding the word would hide the
 * claim's standing along with it.
 */
function confidenceLabel(
  confidence: string | undefined,
  labels: Record<string, string>,
): string {
  if (!confidence) return ''
  return labels[confidence] ?? confidence
}

function operatorName(id: string, bots: readonly CopilotBot[], zh: boolean): string {
  const bot = bots.find((entry) => entry.id === id)
  if (!bot) return id
  return zh ? bot.title_zh : bot.title
}

function HandoffCard({
  handoff,
  bots,
  onSelectOperator,
}: {
  handoff: HandoffResponse
  bots: readonly CopilotBot[]
  onSelectOperator?: (botId: string) => void
}) {
  const { t, language } = useI18n()
  const zh = language === 'zh'
  // The generated types make every defaulted list optional. Normalised once here
  // rather than guarded at each use, so a missing list renders as empty instead
  // of as a crash on a record written before a field existed.
  const claims = handoff.claims ?? []
  const openQuestions = handoff.open_questions ?? []
  const refs = handoff.refs ?? []
  const unsupported = claims.filter((claim) => claim.confidence === 'unsupported')

  return (
    <FramePanel>
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="font-medium text-foreground">
          {operatorName(handoff.from_bot, bots, zh)}
        </span>
        <ArrowRightIcon className="size-3 text-muted-foreground" aria-hidden="true" />
        {onSelectOperator ? (
          // The successor is the one action this view has: reading what was
          // handed over and then having to find the recipient in a dropdown is
          // the handoff protocol working on paper and not on screen.
          <Button
            type="button"
            variant="link"
            size="sm"
            className="h-auto p-0 text-xs"
            onClick={() => onSelectOperator(handoff.to_bot)}
          >
            {operatorName(handoff.to_bot, bots, zh)}
          </Button>
        ) : (
          <span className="font-medium text-foreground">
            {operatorName(handoff.to_bot, bots, zh)}
          </span>
        )}
        {handoff.produced_by_run ? null : (
          // Said plainly rather than left blank: a note with no run behind it has
          // no transcript for anyone to check, which `auditor` reports as
          // unreviewable rather than as clean.
          <Badge variant="secondary" size="sm">
            {t.copilot.chain.noTranscript}
          </Badge>
        )}
      </div>

      <p className="mt-2 text-sm text-foreground">{handoff.summary}</p>

      {unsupported.length > 0 ? (
        <p className="mt-2 flex items-center gap-1 text-xs text-destructive">
          <WarningCircleIcon className="size-3.5 shrink-0" aria-hidden="true" />
          {t.copilot.chain.unsupportedCount.replace('{count}', String(unsupported.length))}
        </p>
      ) : null}

      {claims.length > 0 ? (
        <ul className="mt-2 space-y-1.5">
          {claims.map((claim, index) => (
            <li key={index} className="text-xs">
              <div className="flex flex-wrap items-baseline gap-1.5">
                <Badge
                  variant={CONFIDENCE_VARIANT[claim.confidence ?? ''] ?? 'secondary'}
                  size="sm"
                >
                  {confidenceLabel(claim.confidence, t.copilot.chain.confidence)}
                </Badge>
                <span className="text-foreground">{claim.statement}</span>
              </div>
              {claim.evidence_ref ? (
                <code className="mt-0.5 block break-all text-[11px] text-muted-foreground">
                  {claim.evidence_ref}
                </code>
              ) : (
                <span className="mt-0.5 block text-[11px] text-destructive">
                  {t.copilot.chain.citesNothing}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : null}

      {openQuestions.length > 0 ? (
        <div className="mt-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {t.copilot.chain.openQuestions}
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
            {openQuestions.map((question, index) => (
              <li key={index}>{question}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {refs.length > 0 ? (
        <p className="mt-2 break-all text-[11px] text-muted-foreground">
          {refs.join(' · ')}
        </p>
      ) : null}
    </FramePanel>
  )
}

export function CopilotChain({ onSelectOperator }: { onSelectOperator?: (botId: string) => void }) {
  const { t } = useI18n()
  const { projectId } = useProjectContext()
  const { data: bots } = useCopilotBots()
  const { data: handoffs, isLoading, isError } = useCopilotHandoffs(projectId)

  if (!projectId) {
    return <p className="p-4 text-xs text-muted-foreground">{t.copilot.chain.selectProject}</p>
  }
  if (isLoading) {
    return <p className="p-4 text-xs text-muted-foreground">{t.copilot.chain.loading}</p>
  }
  if (isError) {
    return (
      <Alert variant="destructive" className="m-4">
        <AlertDescription>{t.copilot.chain.failed}</AlertDescription>
      </Alert>
    )
  }
  if (!handoffs || handoffs.length === 0) {
    return (
      <div className="p-4">
        <p className="text-sm font-medium text-foreground">{t.copilot.chain.emptyTitle}</p>
        <p className="mt-1 text-xs text-muted-foreground">{t.copilot.chain.emptyBody}</p>
      </div>
    )
  }

  return (
    <div className="p-4">
      <p className="mb-3 text-xs text-muted-foreground">{t.copilot.chain.intro}</p>
      <Frame spacing="sm">
        {handoffs.map((handoff) => (
          <HandoffCard
            key={handoff.id}
            handoff={handoff}
            bots={bots ?? []}
            onSelectOperator={onSelectOperator}
          />
        ))}
      </Frame>
    </div>
  )
}
