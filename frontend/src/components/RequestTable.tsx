import type { RequestRow } from '../api'
import { formatDateTime, formatIDR, formatMs, formatNumber } from '../format'
import { statusLabel } from '../labels'

interface Props {
  rows: RequestRow[]
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
  showUser?: boolean
}

export function RequestTable({ rows, page, pageSize, total, onPage, showUser = false }: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (total === 0) {
    return (
      <div className="table-wrap empty">
        Belum ada request untuk filter ini. Coba perluas rentang tanggal atau hapus filter.
      </div>
    )
  }
  return (
    <>
      <div className="table-wrap">
        <table className="table table--requests">
          <thead>
            <tr>
              <th scope="col">Waktu</th>
              {showUser && <th scope="col">Pengguna</th>}
              <th scope="col">Model</th>
              <th scope="col">Key dan proyek</th>
              <th scope="col" className="right">
                Token masuk / keluar
              </th>
              <th scope="col" className="right">
                Biaya
              </th>
              <th scope="col" className="right">
                Latensi
              </th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const cache = row.cache_write_tokens + row.cache_read_tokens
              return (
                <tr key={row.request_id}>
                  <td className="num muted">{formatDateTime(row.started_at)}</td>
                  {showUser && <td>{row.user_name ?? '–'}</td>}
                  <td className="nowrap">
                    {row.model ?? '–'}
                    <span className="cell-sub muted">{row.stream ? 'stream' : 'non-stream'}</span>
                  </td>
                  <td className="nowrap">
                    {row.key_name ?? <span className="muted">tanpa key</span>}
                    <span className="cell-sub muted">{row.project ?? 'tanpa proyek'}</span>
                  </td>
                  <td className="num right">
                    {row.usage_estimated && (
                      <abbr title="Estimasi: provider tidak mengirim data token" className="muted">
                        ≈{' '}
                      </abbr>
                    )}
                    {formatNumber(row.input_tokens)} / {formatNumber(row.output_tokens)}
                    {cache > 0 && (
                      <span className="cell-sub muted">
                        cache tulis {formatNumber(row.cache_write_tokens)}, baca{' '}
                        {formatNumber(row.cache_read_tokens)}
                      </span>
                    )}
                  </td>
                  <td className="num right">{formatIDR(row.cost_idr)}</td>
                  <td className="num right muted">
                    {formatMs(row.latency_ms)}
                    {row.ttft_ms !== null && row.stream && (
                      <span className="cell-sub">token pertama {formatMs(row.ttft_ms)}</span>
                    )}
                  </td>
                  <td>
                    <span className="status" data-ok={row.status_code < 400}>
                      {statusLabel(row)}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="pager">
          <span className="muted num">
            Halaman {page} dari {pages}, {formatNumber(total)} request
          </span>
          <span className="chips">
            <button className="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>
              Sebelumnya
            </button>
            <button className="button" disabled={page >= pages} onClick={() => onPage(page + 1)}>
              Berikutnya
            </button>
          </span>
        </div>
      )}
    </>
  )
}
