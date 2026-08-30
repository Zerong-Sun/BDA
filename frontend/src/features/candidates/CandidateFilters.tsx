import { useMemo, useState } from 'react'
import {
  createFilter,
  Filters,
  type Filter,
  type FilterFieldConfig,
} from '@/components/reui/filters'
import { Button } from '@/components/ui/Button'
import { useI18n } from '../../lib/i18n'

interface CandidateFiltersProps {
  search: string
  status: string
  priorityOnly: boolean
  onSearchChange: (value: string) => void
  onStatusChange: (value: string) => void
  onPriorityOnlyChange: (value: boolean) => void
}

type CandidateFilterValue = string | boolean
type CandidateFilter = Filter<CandidateFilterValue>

const candidateStatuses = new Set(['Validated', 'QC risk', 'Retest', 'Reserve'])

function createCandidateFilter(
  field: 'search' | 'status' | 'priority',
  operator: 'contains' | 'is',
  values: CandidateFilterValue[],
  id: string,
): CandidateFilter {
  const filter = createFilter<CandidateFilterValue>(field, operator, values)
  filter.id = id
  return filter
}

function filtersFromQuery(
  search: string,
  status: string,
  priorityOnly: boolean,
  ids: Record<'search' | 'status' | 'priority', string>,
  previous: CandidateFilter[] = [],
): CandidateFilter[] {
  const existing = new Map(previous.map((filter) => [filter.field, filter]))
  const next: CandidateFilter[] = []
  const draft = (field: 'search' | 'status' | 'priority') => {
    const filter = existing.get(field)
    return filter && (filter.values.length === 0 || filter.values[0] === '') ? filter : undefined
  }

  if (search) {
    next.push(createCandidateFilter('search', 'contains', [search], existing.get('search')?.id ?? ids.search))
  } else {
    const searchDraft = draft('search')
    if (searchDraft) next.push(createCandidateFilter('search', 'contains', [''], searchDraft.id))
  }
  if (status !== 'All') {
    next.push(createCandidateFilter('status', 'is', [status], existing.get('status')?.id ?? ids.status))
  } else {
    const statusDraft = draft('status')
    if (statusDraft) next.push(createCandidateFilter('status', 'is', [], statusDraft.id))
  }
  if (priorityOnly) {
    next.push(createCandidateFilter('priority', 'is', [true], existing.get('priority')?.id ?? ids.priority))
  } else {
    const priorityDraft = draft('priority')
    if (priorityDraft) next.push(createCandidateFilter('priority', 'is', [], priorityDraft.id))
  }
  return next
}

export function CandidateFilters({
  search,
  status,
  priorityOnly,
  onSearchChange,
  onStatusChange,
  onPriorityOnlyChange,
}: CandidateFiltersProps) {
  const { t } = useI18n()
  const [filterIds] = useState(() => ({
    search: createFilter('search').id,
    status: createFilter('status').id,
    priority: createFilter('priority').id,
  }))
  const fields = useMemo<FilterFieldConfig<CandidateFilterValue>[]>(() => [
    {
      key: 'search',
      label: t.candidatesExt.filters.search,
      type: 'text',
      defaultOperator: 'contains',
      operators: [{ value: 'contains', label: t.candidatesExt.filters.operatorContains }],
      placeholder: t.candidatesExt.filters.searchPlaceholder,
    },
    {
      key: 'status',
      label: t.candidatesExt.filters.status,
      type: 'select',
      defaultOperator: 'is',
      operators: [{ value: 'is', label: t.candidatesExt.filters.operatorIs }],
      options: [
        { value: 'Validated', label: t.candidatesExt.filters.validated },
        { value: 'QC risk', label: t.candidatesExt.filters.qcRisk },
        { value: 'Retest', label: t.candidatesExt.filters.retest },
        { value: 'Reserve', label: t.candidatesExt.filters.reserve },
      ],
    },
    {
      key: 'priority',
      label: t.candidatesExt.filters.priority,
      type: 'select',
      defaultOperator: 'is',
      operators: [{ value: 'is', label: t.candidatesExt.filters.operatorIs }],
      options: [{ value: true, label: t.candidatesExt.filters.priorityOnly }],
    },
  ], [t])
  const [filterState, setFilterState] = useState(() => ({
    filters: filtersFromQuery(search, status, priorityOnly, filterIds),
    external: { search, status, priorityOnly },
  }))
  const filters = useMemo(() => {
    const externalMatches =
      filterState.external.search === search &&
      filterState.external.status === status &&
      filterState.external.priorityOnly === priorityOnly
    return externalMatches
      ? filterState.filters
      : filtersFromQuery(search, status, priorityOnly, filterIds, filterState.filters)
  }, [filterIds, filterState, priorityOnly, search, status])

  const handleChange = (next: CandidateFilter[]) => {
    const sanitized = next.flatMap((filter): CandidateFilter[] => {
      if (filter.field === 'search' && filter.operator === 'contains') {
        const value = typeof filter.values[0] === 'string' ? filter.values[0] : ''
        return [createCandidateFilter('search', 'contains', [value], filter.id)]
      }
      if (filter.field === 'status' && filter.operator === 'is') {
        const value = typeof filter.values[0] === 'string' && candidateStatuses.has(filter.values[0])
          ? filter.values[0]
          : undefined
        return [createCandidateFilter('status', 'is', value ? [value] : [], filter.id)]
      }
      if (filter.field === 'priority' && filter.operator === 'is') {
        return [createCandidateFilter('priority', 'is', filter.values[0] === true ? [true] : [], filter.id)]
      }
      return []
    })
    setFilterState({
      filters: sanitized,
      external: { search, status, priorityOnly },
    })
    const searchFilter = sanitized.find((filter) => filter.field === 'search')
    const statusFilter = sanitized.find((filter) => filter.field === 'status')
    const priorityFilter = sanitized.find((filter) => filter.field === 'priority')
    const nextSearch = typeof searchFilter?.values[0] === 'string' ? searchFilter.values[0] : ''
    const nextStatus = typeof statusFilter?.values[0] === 'string' ? statusFilter.values[0] : 'All'
    const nextPriorityOnly = priorityFilter?.values[0] === true
    if (nextSearch !== search) onSearchChange(nextSearch)
    if (nextStatus !== status) onStatusChange(nextStatus)
    if (nextPriorityOnly !== priorityOnly) onPriorityOnlyChange(nextPriorityOnly)
  }

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2" data-slot="filters" data-testid="candidate-filters">
      <Filters
        filters={filters}
        fields={fields}
        onChange={handleChange}
        size="sm"
        allowMultiple={false}
        i18n={{
          addFilter: t.candidatesExt.filters.addFilter,
          searchFields: t.candidatesExt.filters.searchPlaceholder,
        }}
      />
      {filters.length > 0 ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            setFilterState({
              filters: [],
              external: { search, status, priorityOnly },
            })
            onSearchChange('')
            onStatusChange('All')
            onPriorityOnlyChange(false)
          }}
        >
          {t.candidatesExt.filters.clearFilters}
        </Button>
      ) : null}
    </div>
  )
}
