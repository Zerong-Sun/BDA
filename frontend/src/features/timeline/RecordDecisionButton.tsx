import { useState } from 'react'
import { NotePencilIcon } from '@phosphor-icons/react'
import { Button } from '../../components/ui/Button'
import { useI18n } from '../../lib/i18n'
import { TimelineEntryEditor } from './TimelineEntryEditor'
import type { DecisionSeed } from './timelineEntryForm'

/**
 * Record a decision from where the work happened, with the evidence already cited.
 *
 * The decision record has one measured failure and it is not a design failure: 97 rulings
 * exist in a Markdown file, 8 reached the table, and `provenance` holds 49 LSF job numbers
 * as strings and no addressable object at all. Forty years of design-rationale research
 * has the same finding under a different name - rationale that costs a separate act to
 * capture does not get captured.
 *
 * So the act moves. A job finishes, a result lands, a candidate is judged; the ids are
 * already in hand at that moment, and the button carries them into a draft. Writing the
 * record becomes a sentence and a click instead of a visit to another page and a retyped
 * identifier.
 *
 * What is seeded is only what the platform *knows*: which run, which half of the loop,
 * what it produced. The conclusion, the outcome and the rejected alternative are left
 * empty on purpose. Prefilling a judgement would be a machine's opinion carrying a
 * person's signature, and this record exists precisely to say whose judgement a thing was.
 */

interface RecordDecisionButtonProps {
  projectId: string
  seed: DecisionSeed
  /** Compact placement inside a row of other controls. */
  size?: 'sm' | 'default'
  className?: string
}

export function RecordDecisionButton({
  projectId,
  seed,
  size = 'sm',
  className,
}: RecordDecisionButtonProps) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size={size}
        className={className}
        onClick={() => setOpen(true)}
      >
        <NotePencilIcon aria-hidden="true" className="size-3.5" />
        {t.timeline.recordDecision}
      </Button>
      {open ? (
        <TimelineEntryEditor projectId={projectId} seed={seed} onClose={() => setOpen(false)} />
      ) : null}
    </>
  )
}
