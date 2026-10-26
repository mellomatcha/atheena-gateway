import { useCallback, useEffect, useState } from 'react'
import {
  api,
  type ApiKey,
  type Facets,
  type RequestPage,
  type Summary,
  type Timeseries,
  type Totals,
} from '../api'
import { RequestTable } from '../components/RequestTable'
import { UsageChart } from '../components/UsageChart'
import { UsageFiltersBar } from '../components/UsageFilters'
import { filterQuery, useUsageFilters } from '../filters'
import { formatIDR, formatNumber } from '../format'
import { useAsync } from '../useAsync'
import { Link } from 'react-router'
import { useMe } from '../session-context'

type Unit = 'idr' | 'token'

function Stat({ label, totals }: { label: string; totals: Totals | undefined }) {
  return (
    <div className="stat">
      <dt className="stat__label">{label}</dt>
      <dd className="stat__value num money">{totals ? formatIDR(totals.cost_idr) : '…'}</dd>
      <dd className="stat__sub num muted">
        {totals
          ? `${formatNumber(totals.tokens)} token, ${formatNumber(totals.requests)} request`
          : ''}
      </dd>
    </div>
  )
}

export function OverviewPage() {
  const { me } = useMe()
  const [filters, setFilters] = useUsageFilters()
  const [unit, setUnit] = useState<Unit>('token')
  const [page, setPage] = useState(1)
  const query = filterQuery(filters)
  const queryKey = new URLSearchParams(query).toString()

  const summary = useAsync('summary', () => api<Summary>('/usage/summary'))
  const facets = useAsync('facets', () => api<Facets>('/usage/facets'))
  const keys = useAsync('keys', () => api<ApiKey[]>('/keys'))
  const series = useAsync(`series?${queryKey}&unit=${unit}`, () =>
    api<Timeseries>('/usage/timeseries', { query: { ...query, unit } }),
  )
  const log = useAsync(`log?${queryKey}&page=${page}`, () =>
    api<RequestPage>('/usage/requests', { query: { ...query, page } }),
  )
  const { reload: reloadSummary } = summary
  const { reload: reloadFacets } = facets
  const { reload: reloadKeys } = keys
  const { reload: reloadSeries } = series
  const { reload: reloadLog } = log
  const refreshUsage = useCallback(() => {
    reloadSummary()
    reloadFacets()
    reloadKeys()
    reloadSeries()
    reloadLog()
  }, [reloadSummary, reloadFacets, reloadKeys, reloadSeries, reloadLog])
  useEffect(() => {
    const refreshVisible = () => {
      if (document.visibilityState === 'visible') refreshUsage()
    }
    const timer = window.setInterval(refreshVisible, 30_000)
    document.addEventListener('visibilitychange', refreshVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', refreshVisible)
    }
  }, [refreshUsage])

  function changeFilters(next: Parameters<typeof setFilters>[0]) {
    setPage(1)
    setFilters(next)
  }

  const exportHref = `/app/api/usage/export.csv?${queryKey}`
  const range = series.data?.range_totals

  return (
    <div className="page">
      <header className="workspace-welcome">
        <div>
          <span className="eyebrow">ATHEENA / YOUR WORKSPACE</span>
          <h1>
            Selamat datang,
            <br />
            {me.full_name}.
          </h1>
          <p>Model pilihanmu. Kendali di tanganmu.</p>
          <Link className="button button--primary" to="/app/keys">
            Kelola API key ↗
          </Link>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <span>ΑΘΗΝΑ</span>
          <img src="/brand/athena.png" alt="" />
        </div>
      </header>

      <dl className="stats">
        <Stat label="Hari ini" totals={summary.data?.today} />
        <Stat label="7 hari terakhir" totals={summary.data?.last_7_days} />
        <Stat label="30 hari terakhir" totals={summary.data?.last_30_days} />
        <div className="stat">
          <dt className="stat__label">Model paling sering, 30 hari</dt>
          <dd className="stat__value stat__value--text">
            {summary.data ? (summary.data.top_model_30_days ?? 'Belum ada') : '…'}
          </dd>
        </div>
      </dl>
      {summary.error && <p className="notice notice--error">{summary.error.message}</p>}

      <div className="section__head">
        <p className="muted">
          Data diperbarui setiap 30 detik saat halaman terbuka. Waktu mengikuti WIB.
        </p>
        <button
          className="button"
          onClick={refreshUsage}
          disabled={summary.loading || series.loading || log.loading}
        >
          Perbarui pemakaian
        </button>
      </div>

      <section className="section" aria-labelledby="grafik">
        <div className="section__head">
          <h2 id="grafik">Pemakaian per hari</h2>
          <div className="segmented" role="group" aria-label="Satuan grafik">
            <button type="button" aria-pressed={unit === 'idr'} onClick={() => setUnit('idr')}>
              Rupiah
            </button>
            <button type="button" aria-pressed={unit === 'token'} onClick={() => setUnit('token')}>
              Token
            </button>
          </div>
        </div>
        <UsageFiltersBar
          filters={filters}
          onChange={changeFilters}
          facets={facets.data}
          keys={keys.data}
        />
        {series.error && <p className="notice notice--error">{series.error.message}</p>}
        {unit === 'idr' && range && range.tokens > 0 && range.cost_idr === 0 && (
          <p className="notice">
            Token sudah tercatat. Biaya pada rentang ini Rp0; pilih Token untuk melihat volume
            pemakaian.
          </p>
        )}
        <div className="panel chart-panel" aria-busy={series.loading}>
          {range && (
            <p className="chart-panel__total">
              <span className="num">
                {unit === 'idr' ? formatIDR(range.cost_idr) : `${formatNumber(range.tokens)} token`}
              </span>{' '}
              <span className="muted">
                dari {formatNumber(range.requests)} request pada rentang ini
              </span>
            </p>
          )}
          {series.data ? (
            <UsageChart points={series.data.points} unit={unit} />
          ) : (
            <div className="chart chart--loading" />
          )}
        </div>
      </section>

      <section className="section" aria-labelledby="log">
        <div className="section__head">
          <h2 id="log">Log request</h2>
          <a className="button" href={exportHref} download>
            Ekspor CSV
          </a>
        </div>
        {log.error && <p className="notice notice--error">{log.error.message}</p>}
        {log.data && (
          <RequestTable
            rows={log.data.items}
            page={log.data.page}
            pageSize={log.data.page_size}
            total={log.data.total}
            onPage={setPage}
          />
        )}
      </section>
    </div>
  )
}
