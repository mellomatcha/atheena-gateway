import { useState } from 'react'
import { api, type RequestPage, type Timeseries, type UserSummary } from '../../api'
import type { AdminModel, Breakdown, GlobalUsage, Project } from '../../admin-types'
import { Field, Feedback, PageHead } from '../../components/AdminUI'
import { RequestTable } from '../../components/RequestTable'
import { UsageChart } from '../../components/UsageChart'
import { UsageFiltersBar } from '../../components/UsageFilters'
import { filterQuery, useUsageFilters } from '../../filters'
import { formatIDR, formatNumber, todayWib } from '../../format'
import { useAsync } from '../../useAsync'

function BreakdownTable({ rows }: { rows: Breakdown[] }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Nama</th>
            <th className="right">Request</th>
            <th className="right">Token</th>
            <th className="right">Biaya</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key ?? '__none'}>
              <td>{r.label}</td>
              <td className="right num">{formatNumber(r.totals.requests)}</td>
              <td className="right num">{formatNumber(r.totals.tokens)}</td>
              <td className="right num">{formatIDR(r.totals.cost_idr)}</td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={4}>Belum ada pemakaian pada periode ini.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
export function UsagePage() {
  const [filters, setFilters] = useUsageFilters()
  const [user, setUser] = useState('')
  const [unit, setUnit] = useState<'idr' | 'token'>('idr')
  const [group, setGroup] = useState<'by_user' | 'by_model' | 'by_project' | 'by_provider'>(
    'by_user',
  )
  const [page, setPage] = useState(1)
  const query = { ...filterQuery(filters), user }
  const key = new URLSearchParams(query).toString()
  const users = useAsync('admin-users', () => api<UserSummary[]>('/admin/users'))
  const models = useAsync('admin-models', () => api<AdminModel[]>('/admin/models'))
  const projects = useAsync('admin-projects', () => api<Project[]>('/admin/projects'))
  const summary = useAsync(`global:${key}`, () =>
    api<GlobalUsage>('/admin/usage/summary', { query }),
  )
  const series = useAsync(`series:${key}:${unit}`, () =>
    api<Timeseries>('/admin/usage/timeseries', { query: { ...query, unit } }),
  )
  const log = useAsync(`requests:${key}:${page}`, () =>
    api<RequestPage>('/admin/usage/requests', { query: { ...query, page } }),
  )
  const [month, setMonth] = useState(todayWib().slice(0, 7))
  const [by, setBy] = useState<'project' | 'user'>('project')
  const report = useAsync(`report:${month}:${by}`, () =>
    api<{ rows: Breakdown[] }>('/admin/reports/monthly', { query: { month, by } }),
  )
  return (
    <div className="page">
      <PageHead
        title="Pemakaian global"
        description="Pantau request seluruh workspace dan unduh laporan biaya per pengguna atau proyek."
      />
      <Field label="Pengguna">
        <select
          className="input"
          value={user}
          onChange={(e) => {
            setUser(e.target.value)
            setPage(1)
          }}
        >
          <option value="">Semua pengguna</option>
          {users.data?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.display_name} · {u.email}
            </option>
          ))}
        </select>
      </Field>
      <UsageFiltersBar
        filters={filters}
        onChange={(next) => {
          setPage(1)
          setFilters(next)
        }}
        facets={{
          models: models.data?.map((m) => m.public_name) ?? [],
          projects: projects.data?.map((p) => p.slug) ?? [],
        }}
        keys={undefined}
      />
      <Feedback
        error={
          summary.error?.message ??
          series.error?.message ??
          log.error?.message ??
          users.error?.message ??
          models.error?.message ??
          projects.error?.message
        }
      />
      {summary.data && (
        <dl className="stats">
          <div className="stat">
            <dt className="stat__label">Biaya periode ini</dt>
            <dd className="stat__value num">{formatIDR(summary.data.totals.cost_idr)}</dd>
          </div>
          <div className="stat">
            <dt className="stat__label">Request</dt>
            <dd className="stat__value num">{formatNumber(summary.data.totals.requests)}</dd>
          </div>
          <div className="stat">
            <dt className="stat__label">Token</dt>
            <dd className="stat__value num">{formatNumber(summary.data.totals.tokens)}</dd>
          </div>
        </dl>
      )}
      <section className="section">
        <div className="section__head">
          <h2>Pemakaian harian</h2>
          <div className="segmented">
            <button aria-pressed={unit === 'idr'} onClick={() => setUnit('idr')}>
              Rupiah
            </button>
            <button aria-pressed={unit === 'token'} onClick={() => setUnit('token')}>
              Token
            </button>
          </div>
        </div>
        <div className="panel chart-panel" aria-busy={series.loading}>
          {series.data ? (
            <UsageChart points={series.data.points} unit={unit} />
          ) : (
            <p>Memuat grafik…</p>
          )}
        </div>
      </section>
      <section className="section">
        <Field label="Rincian berdasarkan">
          <select
            className="input"
            value={group}
            onChange={(e) => setGroup(e.target.value as typeof group)}
          >
            <option value="by_user">Pengguna</option>
            <option value="by_model">Model</option>
            <option value="by_project">Proyek</option>
            <option value="by_provider">Provider</option>
          </select>
        </Field>
        {summary.data && <BreakdownTable rows={summary.data[group]} />}
      </section>
      <section className="section">
        <div className="section__head">
          <h2>Log request</h2>
          <a className="button" download href={`/app/api/admin/usage/export.csv?${key}`}>
            Ekspor CSV
          </a>
        </div>
        {log.data && (
          <RequestTable
            rows={log.data.items}
            page={log.data.page}
            pageSize={log.data.page_size}
            total={log.data.total}
            onPage={setPage}
            showUser
          />
        )}
      </section>
      <section className="section">
        <h2>Laporan bulanan</h2>
        <div className="filters__row">
          <Field label="Bulan">
            <input
              className="input"
              type="month"
              value={month}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
            />
          </Field>
          <Field label="Kelompok">
            <select
              className="input"
              value={by}
              onChange={(e) => setBy(e.target.value as typeof by)}
            >
              <option value="project">Proyek</option>
              <option value="user">Pengguna</option>
            </select>
          </Field>
          <a
            className="button"
            download
            href={`/app/api/admin/reports/monthly.csv?month=${encodeURIComponent(month)}&by=${by}`}
          >
            Unduh laporan
          </a>
        </div>
        <Feedback error={report.error?.message} />
        {report.data && <BreakdownTable rows={report.data.rows} />}
      </section>
    </div>
  )
}
