import { useI18n } from '../../lib/i18n'
import { Badge } from '../../components/reui/badge'
import { Button } from '../../components/ui/Button'
import type { WorkflowRun } from '../../lib/schemas/workflow'

interface RunLineageProps {
  run: Pick<WorkflowRun, 'arm_label' | 'varied_parameters' | 'derived_from_id'>
  onOpenBaseline?: (runId: string) => void
}

/**
 * What this run changed relative to the one it is compared against.
 *
 * The label and the parameter list are computed by the platform from the stored node
 * parameters, never typed by the author, so this panel is evidence rather than a
 * description: a run presented as a single-variable control shows exactly one row here,
 * and one that quietly changed three shows three.
 */
export function RunLineage({ run, onOpenBaseline }: RunLineageProps) {
  const { t } = useI18n()
  const labels = t.workflowExt.lineage

  const changes = Object.entries(run.varied_parameters ?? {}).flatMap(([nodeKey, nodeDiff]) =>
    Object.entries(nodeDiff ?? {}).map(([name, change]) => ({ nodeKey, name, change })),
  )

  if (!run.derived_from_id) {
    return (
      <div className="flex items-center gap-2 text-xs text-text-secondary">
        <Badge variant="outline">{labels.baseline}</Badge>
        <span>{labels.baselineHint}</span>
      </div>
    )
  }

  const isReplicate = run.arm_label === 'replicate'

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge variant={isReplicate ? 'secondary' : 'success-light'}>
          {isReplicate ? labels.replicate : labels.variant}
        </Badge>
        <span className="text-text-secondary">
          {isReplicate
            ? labels.replicateHint
            : changes.length === 1
              ? labels.singleVariable
              : format(labels.multiVariable, { count: String(changes.length) })}
        </span>
        {onOpenBaseline ? (
          <Button
            type="button"
            variant="link"
            size="sm"
            className="h-auto p-0 text-xs"
            onClick={() => onOpenBaseline(run.derived_from_id as string)}
          >
            {labels.openBaseline}
          </Button>
        ) : null}
      </div>

      {changes.length > 0 ? (
        <div role="table" className="w-full text-xs">
          <div role="row" className="grid grid-cols-3 gap-2 pb-1 text-text-secondary">
            <span role="columnheader">{labels.parameter}</span>
            <span role="columnheader">{labels.from}</span>
            <span role="columnheader">{labels.to}</span>
          </div>
          {changes.map(({ nodeKey, name, change }) => (
            <div
              role="row"
              key={`${nodeKey}.${name}`}
              className="grid grid-cols-3 gap-2 border-t border-border-soft py-1"
            >
              <span role="cell" className="font-mono">
                {name}
                <span className="ml-1 text-text-muted">{nodeKey}</span>
              </span>
              <span role="cell" className="font-mono text-text-secondary">{render(change.from)}</span>
              <span role="cell" className="font-mono text-text-primary">{render(change.to)}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function render(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value === '' ? '(empty)' : value
  return JSON.stringify(value)
}

function format(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_match, key: string) => values[key] ?? `{${key}}`)
}
