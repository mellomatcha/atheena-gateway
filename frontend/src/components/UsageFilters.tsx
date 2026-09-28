import type { ApiKey, Facets } from '../api'
import { shiftDay, todayWib } from '../format'
import type { UsageFilters } from '../filters'

interface Props {
  filters: UsageFilters
  onChange: (next: Partial<UsageFilters>) => void
  facets: Facets | undefined
  keys: ApiKey[] | undefined
}

const PRESETS = [
  { label: '7 hari', days: 7 },
  { label: '30 hari', days: 30 },
  { label: '90 hari', days: 90 },
]

export function UsageFiltersBar({ filters, onChange, facets, keys }: Props) {
  const today = todayWib()
  const activePreset = PRESETS.find(
    (p) => filters.to === today && filters.from === shiftDay(today, -(p.days - 1)),
  )
  const hasExtra = Boolean(filters.model || filters.key || filters.project || filters.status)

  return (
    <div className="filters" role="group" aria-label="Filter pemakaian">
      <div className="filters__row">
      <div className="segmented" role="group" aria-label="Rentang cepat">
        {PRESETS.map((preset) => (
          <button
            key={preset.days}
            type="button"
            aria-pressed={activePreset?.days === preset.days}
            onClick={() => onChange({ from: shiftDay(today, -(preset.days - 1)), to: today })}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <label className="field">
        <span className="field__label">Dari</span>
        <input
          className="input"
          type="date"
          value={filters.from}
          max={filters.to}
          onChange={(e) => e.target.value && onChange({ from: e.target.value })}
        />
      </label>
      <label className="field">
        <span className="field__label">Sampai</span>
        <input
          className="input"
          type="date"
          value={filters.to}
          min={filters.from}
          max={today}
          onChange={(e) => e.target.value && onChange({ to: e.target.value })}
        />
      </label>
      </div>
      <div className="filters__row">
      <label className="field">
        <span className="field__label">Model</span>
        <select className="input" value={filters.model} onChange={(e) => onChange({ model: e.target.value })}>
          <option value="">Semua model</option>
          {facets?.models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span className="field__label">Key</span>
        <select className="input" value={filters.key} onChange={(e) => onChange({ key: e.target.value })}>
          <option value="">Semua key</option>
          {keys?.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name} ({k.prefix}…){k.status === 'revoked' ? ', dicabut' : ''}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span className="field__label">Proyek</span>
        <select
          className="input"
          value={filters.project}
          onChange={(e) => onChange({ project: e.target.value })}
        >
          <option value="">Semua proyek</option>
          <option value="none">Tanpa proyek</option>
          {facets?.projects.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span className="field__label">Status</span>
        <select
          className="input"
          value={filters.status}
          onChange={(e) => onChange({ status: e.target.value as UsageFilters['status'] })}
        >
          <option value="">Semua status</option>
          <option value="success">Sukses</option>
          <option value="failed">Gagal</option>
        </select>
      </label>
      {hasExtra && (
        <button
          type="button"
          className="button filters__reset"
          onClick={() => onChange({ model: '', key: '', project: '', status: '' })}
        >
          Hapus filter
        </button>
      )}
      </div>
    </div>
  )
}
