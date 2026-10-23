import { useState } from 'react'
import { api } from '../../api'
import { Field, Feedback, PageHead } from '../../components/AdminUI'
import { formatDateTime } from '../../format'
import { useAsync } from '../../useAsync'

interface AuditPageData {
  items: {
    id: string
    created_at: string
    actor_name: string | null
    action: string
    target_label: string | null
    target_id: string
    before: unknown
    after: unknown
  }[]
  page: number
  page_size: number
  total: number
  actions: string[]
}
export function AuditPage() {
  const [page, setPage] = useState(1)
  const [action, setAction] = useState('')
  const log = useAsync(`audit:${page}:${action}`, () =>
    api<AuditPageData>('/admin/audit-logs', { query: { page, action } }),
  )
  const pages = log.data ? Math.max(1, Math.ceil(log.data.total / log.data.page_size)) : 1
  return (
    <div className="page">
      <PageHead
        title="Audit log"
        description="Jejak perubahan akses, harga, saldo, dan pengaturan, lengkap dengan nilai sebelum dan sesudah."
      />
      <Field label="Jenis perubahan">
        <select
          className="input"
          value={action}
          onChange={(e) => {
            setAction(e.target.value)
            setPage(1)
          }}
        >
          <option value="">Semua perubahan</option>
          {log.data?.actions.map((a) => (
            <option key={a}>{a}</option>
          ))}
        </select>
      </Field>
      <Feedback error={log.error?.message} />
      {log.loading && <p role="status">Memuat audit…</p>}
      {log.data && (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Waktu / pelaku</th>
                  <th>Perubahan</th>
                  <th>Rincian</th>
                </tr>
              </thead>
              <tbody>
                {log.data.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {formatDateTime(row.created_at)}
                      <br />
                      <span className="muted">{row.actor_name ?? 'Sistem'}</span>
                    </td>
                    <td>
                      <strong>{row.action}</strong>
                      <br />
                      {row.target_label ?? row.target_id}
                    </td>
                    <td>
                      <details>
                        <summary>Lihat perubahan</summary>
                        <div className="audit-values">
                          <div>
                            <h3>Sebelum</h3>
                            <pre>{JSON.stringify(row.before, null, 2) ?? '—'}</pre>
                          </div>
                          <div>
                            <h3>Sesudah</h3>
                            <pre>{JSON.stringify(row.after, null, 2) ?? '—'}</pre>
                          </div>
                        </div>
                      </details>
                    </td>
                  </tr>
                ))}
                {!log.data.items.length && (
                  <tr>
                    <td colSpan={3}>Belum ada perubahan untuk filter ini.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="actions">
            <button
              className="button"
              disabled={page <= 1 || log.loading}
              onClick={() => setPage(page - 1)}
            >
              Sebelumnya
            </button>
            <span>
              Halaman {page} / {pages}
            </span>
            <button
              className="button"
              disabled={page >= pages || log.loading}
              onClick={() => setPage(page + 1)}
            >
              Berikutnya
            </button>
          </div>
        </>
      )}
    </div>
  )
}
