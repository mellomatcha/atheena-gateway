import type { LedgerEntry, LedgerType } from '../api'
import { formatDateTime, formatIDR, formatSignedIDR } from '../format'

const LABELS: Record<LedgerType, string> = {
  topup: 'Top-up',
  usage: 'Pemakaian',
  adjustment: 'Penyesuaian',
  refund: 'Pengembalian',
}

interface Props {
  items: LedgerEntry[]
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
  emptyText: string
}

export function LedgerTable({ items, page, pageSize, total, onPage, emptyText }: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (total === 0) return <div className="table-wrap empty">{emptyText}</div>

  return (
    <>
      <div className="table-wrap">
        <table className="table table--ledger">
          <thead>
            <tr>
              <th scope="col">Waktu</th>
              <th scope="col">Keterangan</th>
              <th scope="col" className="right">
                Jumlah
              </th>
              <th scope="col" className="right">
                Saldo setelahnya
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((entry) => (
              <tr key={entry.id}>
                <td className="num muted">{formatDateTime(entry.created_at)}</td>
                <td>
                  {LABELS[entry.type]}
                  {entry.note && <span className="muted">: {entry.note}</span>}
                </td>
                <td className={`num right ${entry.amount_idr > 0 ? 'amount--credit' : ''}`}>
                  {formatSignedIDR(entry.amount_idr)}
                </td>
                <td className="num right ledger__after">
                  <span className="ledger__after-label muted">Saldo </span>
                  {formatIDR(entry.balance_after_idr)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="pager">
          <span className="muted num">
            Halaman {page} dari {pages}
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
