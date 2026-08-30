import { GlossaryTooltip } from '../../components/ui/GlossaryTooltip'
import { useI18n } from '../../lib/i18n'

interface ScoreBarsProps {
  affinity: number | null | undefined
  stability: number | null | undefined
  solubility: number | null | undefined
  rosettaScore: number | null | undefined
}

interface MetricHelp {
  description: string
  good?: string
}

function Bar({ label, value, help }: { label: string; value: number | null | undefined; help: MetricHelp }) {
  const { t } = useI18n()
  const hasValue = typeof value === 'number'
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-text-secondary">
        <GlossaryTooltip label={label} description={help.description} good={help.good} />
        <span>{hasValue ? value : t.candidatesExt.table.notScored}</span>
      </div>
      <progress className="h-2 w-full accent-accent" value={hasValue ? value : 0} max={100} />
    </div>
  )
}

export function ScoreBars({ affinity, stability, solubility, rosettaScore }: ScoreBarsProps) {
  const { t } = useI18n()

  return (
    <div className="space-y-3">
      <Bar
        label={t.candidatesExt.scoreBars.modelInterfaceScore}
        value={affinity}
        help={{
          description: t.candidatesExt.scoreBars.modelInterfaceScoreHelp,
          good: t.candidatesExt.scoreBars.modelInterfaceScoreGood,
        }}
      />
      <Bar
        label={t.candidatesExt.scoreBars.structureConfidence}
        value={stability}
        help={{
          description: t.candidatesExt.scoreBars.structureConfidenceHelp,
          good: t.candidatesExt.scoreBars.structureConfidenceGood,
        }}
      />
      <Bar
        label={t.candidatesExt.scoreBars.solubilityScore}
        value={solubility}
        help={{
          description: t.candidatesExt.scoreBars.solubilityScoreHelp,
          good: t.candidatesExt.scoreBars.solubilityScoreGood,
        }}
      />
      <div>
        <div className="mb-1 flex justify-between text-xs text-text-secondary">
          <GlossaryTooltip
            label={t.candidatesExt.scoreBars.rosettaInterfaceEnergy}
            description={t.candidatesExt.scoreBars.rosettaInterfaceEnergyHelp}
            good={t.candidatesExt.scoreBars.rosettaInterfaceEnergyGood}
          />
          <span>{rosettaScore ?? '—'}</span>
        </div>
        <p className="text-xs text-text-secondary">{t.candidatesExt.scoreBars.rosettaNotNormalized}</p>
      </div>
    </div>
  )
}
