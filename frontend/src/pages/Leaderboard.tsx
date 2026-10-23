import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api'
import { Field, Feedback, PageHead } from '../components/AdminUI'
import { formatIDR, formatNumber, formatShortDay } from '../format'
import { useAsync } from '../useAsync'

interface Board {
  start: string
  end: string
  me_opted_out: boolean
  efficiency_min_requests: number
  entries: { rank: number; username: string; value: number; requests: number; is_me: boolean }[]
}
export function LeaderboardPage() {
  const [period, setPeriod] = useState('week')
  const [metric, setMetric] = useState('tokens')
  const board = useAsync(`board:${period}:${metric}`, () =>
    api<Board>('/leaderboard', { query: { period, metric } }),
  )
  const labels: Record<string, string> = {
    tokens: 'Token',
    requests: 'Request',
    cost: 'Biaya',
    efficiency: 'Efisiensi cache',
  }
  return (
    <div className="page">
      <PageHead
        title="Leaderboard"
        description="Lihat aktivitas workspace. Hanya username yang dibagikan; nama lengkap dan email tetap privat."
      />
      <div className="filters__row">
        <Field label="Periode">
          <select className="input" value={period} onChange={(e) => setPeriod(e.target.value)}>
            <option value="week">Minggu ini</option>
            <option value="month">Bulan ini</option>
          </select>
        </Field>
        <Field label="Urut berdasarkan">
          <select className="input" value={metric} onChange={(e) => setMetric(e.target.value)}>
            {Object.entries(labels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Link className="button" to="/app/profil">
          Atur privasi
        </Link>
      </div>
      <Feedback error={board.error?.message} />
      {board.loading && <p role="status">Memuat peringkat…</p>}
      {board.data && (
        <>
          {board.data.me_opted_out && (
            <p className="notice">Nama Anda disembunyikan dari leaderboard.</p>
          )}
          <p className="muted">
            {formatShortDay(board.data.start)} – {formatShortDay(board.data.end)} WIB · Diperbarui
            berkala dari pemakaian harian.
            {metric === 'efficiency' && ` Minimal ${board.data.efficiency_min_requests} request.`}
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Peringkat</th>
                  <th>Username</th>
                  <th className="right">{labels[metric]}</th>
                  <th className="right">Request</th>
                </tr>
              </thead>
              <tbody>
                {board.data.entries.map((e) => (
                  <tr key={e.rank} className={e.is_me ? 'row--me' : ''}>
                    <td className="num">{String(e.rank).padStart(2, '0')}</td>
                    <td>
                      <strong>@{e.username}</strong>
                      {e.is_me && <span className="badge">Anda</span>}
                    </td>
                    <td className="num right">
                      {metric === 'cost'
                        ? formatIDR(e.value)
                        : metric === 'efficiency'
                          ? `${(e.value * 100).toFixed(1)}%`
                          : formatNumber(e.value)}
                    </td>
                    <td className="num right">{formatNumber(e.requests)}</td>
                  </tr>
                ))}
                {!board.data.entries.length && (
                  <tr>
                    <td colSpan={4}>Belum ada pemakaian yang memenuhi kriteria periode ini.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
