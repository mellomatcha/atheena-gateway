import { useSearchParams } from 'react-router'
import { shiftDay, todayWib } from './format'

export interface UsageFilters {
  from: string
  to: string
  model: string
  key: string
  project: string
  status: '' | 'success' | 'failed'
}

const KEYS = ['from', 'to', 'model', 'key', 'project', 'status'] as const

/** Usage filters kept in the URL so a filtered view can be bookmarked or shared. */
export function useUsageFilters(): [UsageFilters, (next: Partial<UsageFilters>) => void] {
  const [params, setParams] = useSearchParams()
  const today = todayWib()
  const filters: UsageFilters = {
    from: params.get('from') ?? shiftDay(today, -29),
    to: params.get('to') ?? today,
    model: params.get('model') ?? '',
    key: params.get('key') ?? '',
    project: params.get('project') ?? '',
    status: (params.get('status') as UsageFilters['status']) ?? '',
  }

  function update(next: Partial<UsageFilters>) {
    const merged = { ...filters, ...next }
    const out = new URLSearchParams()
    for (const key of KEYS) {
      if (merged[key]) out.set(key, merged[key])
    }
    setParams(out, { replace: true })
  }

  return [filters, update]
}

export function filterQuery(filters: UsageFilters): Record<string, string> {
  const query: Record<string, string> = {}
  for (const key of KEYS) {
    if (filters[key]) query[key] = filters[key]
  }
  return query
}
