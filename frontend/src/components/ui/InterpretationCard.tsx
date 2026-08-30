import { ArrowRightIcon, WarningCircleIcon } from '@phosphor-icons/react'
import type { InterpretationReasoning, ScoreSignal } from '../../lib/api/copilot'
import { StatusPill } from './StatusPill'
import { useI18n } from '../../lib/i18n'
import { AppFrame } from './AppFrame'

const DECISION_TONE: Record<InterpretationReasoning['decision'], 'green' | 'amber' | 'red' | 'neutral'> = {
  advance: 'green',
  hold: 'amber',
  redesign: 'red',
  insufficient_data: 'neutral',
}

const ASSESSMENT_TONE: Record<ScoreSignal['assessment'], string> = {
  favorable: 'border-success/40 bg-success/10 text-success',
  neutral: 'border-border-soft bg-bg-app text-text-secondary',
  unfavorable: 'border-danger/40 bg-danger/10 text-danger',
  unknown: 'border-border-soft bg-bg-app text-text-secondary',
}

export function InterpretationCard({ reasoning }: { reasoning: InterpretationReasoning }) {
  const { t } = useI18n()
  const ic = t.shared.interpretationCard
  const decisionLabels: Record<InterpretationReasoning['decision'], string> = {
    advance: ic.decisionAdvance,
    hold: ic.decisionHold,
    redesign: ic.decisionRedesign,
    insufficient_data: ic.decisionInsufficientData,
  }

  return (
    <AppFrame panelClassName="p-4 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold text-text-primary">{reasoning.headline}</h3>
        <StatusPill label={decisionLabels[reasoning.decision]} tone={DECISION_TONE[reasoning.decision]} />
      </div>
      <p className="mt-2 text-text-secondary">{reasoning.decision_rationale}</p>

      {reasoning.signals.length > 0 ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {reasoning.signals.map((signal) => (
            <div key={signal.metric} className={`rounded border p-2 text-xs ${ASSESSMENT_TONE[signal.assessment]}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{signal.metric}</span>
                <span>{signal.value}</span>
              </div>
              <p className="mt-1 opacity-90">{signal.rationale}</p>
            </div>
          ))}
        </div>
      ) : null}

      {reasoning.next_actions.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs uppercase tracking-wide text-accent">{ic.nextActions}</p>
          <ul className="mt-1 grid gap-1">
            {reasoning.next_actions.map((action) => (
              <li key={action} className="flex items-start gap-1.5 text-xs text-text-primary">
                <ArrowRightIcon className="mt-0.5 h-3 w-3 shrink-0 text-accent" />
                {action}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {reasoning.caveats.length > 0 ? (
        <div className="mt-3 grid gap-1">
          {reasoning.caveats.map((caveat) => (
            <p key={caveat} className="flex items-start gap-1.5 text-xs text-accent-2">
              <WarningCircleIcon className="mt-0.5 h-3 w-3 shrink-0" />
              {caveat}
            </p>
          ))}
        </div>
      ) : null}
    </AppFrame>
  )
}
