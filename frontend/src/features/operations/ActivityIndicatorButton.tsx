import { useQuery } from '@tanstack/react-query'
import { PulseIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import { useAppStore } from '../../lib/store/appStore'
import { useI18n } from '../../lib/i18n'
import { isSettled, listOperations } from '../../lib/api/operations'

/**
 * Opens Activity, and says when something is still running.
 *
 * The count is the reason the button earns a place in the top bar at all: without it
 * this is a drawer nobody remembers to open, and the defect it fixes - losing track of
 * work that outlives the page you started it on - stays unfixed in practice.
 */
export function ActivityIndicatorButton() {
  const { t, format } = useI18n()
  const { activityOpen, setActivityOpen } = useAppStore()

  const unsettled = useQuery({
    queryKey: ['operations', 'unsettled'],
    queryFn: () => listOperations({ mine: true, limit: 20 }),
    select: (page) => page.items.filter((item) => !isSettled(item)).length,
    staleTime: 10_000,
    // Idle most of the time; quickens only while the user has work in flight.
    refetchInterval: (result) => (result.state.data ? 8000 : 30_000),
  })

  const count = unsettled.data ?? 0
  const label = count
    ? `${t.operations.toggleTitle} — ${format(t.operations.unsettledCount, { count })}`
    : t.operations.toggleTitle

  return (
    <Button
      type="button"
      aria-label={label}
      title={label}
      variant={activityOpen ? 'secondary' : 'outline'}
      size="icon-sm"
      onClick={() => setActivityOpen(!activityOpen)}
    >
      <span className="relative inline-flex">
        <PulseIcon className="h-4 w-4" />
        {count ? (
          <span
            aria-hidden="true"
            className="absolute -right-1 -top-1 h-1.5 w-1.5 rounded-full bg-accent"
          />
        ) : null}
      </span>
    </Button>
  )
}
