import { useState, type FormEvent } from 'react'
import { api, ApiError, type LedgerPage, type UserSummary } from '../api'
import { LedgerTable } from '../components/LedgerTable'
import { formatIDR, formatNumber, parseDigits } from '../format'
import { useMe } from '../session-context'
import { useAsync } from '../useAsync'

type EntryKind = 'topup' | 'adjustment'
type Direction = 'credit' | 'debit'

interface EntryResult {
  entry_id: string
  user: UserSummary
  balance_before_idr: number
  balance_after_idr: number
}

export function AdminBalancePage() {
  const { me, refresh: refreshMe } = useMe()
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string>()
  const users = useAsync(`users?q=${query}`, () =>
    api<UserSummary[]>('/admin/users', { query: { q: query } }),
  )
  const selected = users.data?.find((u) => u.id === selectedId)

  return (
    <div className="page">
      <header className="page__head">
        <h1>Saldo pengguna</h1>
        <p className="muted">
          Tambahkan saldo setelah bukti transfer WhatsApp diperiksa, atau koreksi saldo dengan
          penyesuaian. Setiap perubahan tercatat di ledger dan audit log.
        </p>
      </header>

      <div className="admin-balance">
        <section className="section" aria-labelledby="daftar-user">
          <h2 id="daftar-user" className="visually-hidden">
            Daftar pengguna
          </h2>
          <label className="field">
            <span className="field__label">Cari nama atau email</span>
            <input
              className="input"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          {users.error && <p className="notice notice--error">{users.error.message}</p>}
          {users.data && users.data.length === 0 && (
            <div className="table-wrap empty">Tidak ada pengguna yang cocok dengan "{query}".</div>
          )}
          {users.data && users.data.length > 0 && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Pengguna</th>
                    <th scope="col">Status</th>
                    <th scope="col" className="right">
                      Saldo
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {users.data.map((user) => (
                    <tr
                      key={user.id}
                      data-selectable="true"
                      aria-selected={user.id === selectedId}
                      tabIndex={0}
                      onClick={() => setSelectedId(user.id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          setSelectedId(user.id)
                        }
                      }}
                    >
                      <td>
                        {user.display_name}
                        <br />
                        <span className="muted">{user.email}</span>
                      </td>
                      <td className="muted">{user.status === 'active' ? 'Aktif' : user.status}</td>
                      <td className="num right">{formatIDR(user.balance_idr)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {selected ? (
          <UserBalance
            key={selected.id}
            user={selected}
            onChanged={() => {
              users.reload()
              if (selected.id === me.id) void refreshMe()
            }}
          />
        ) : (
          <div className="panel empty">Pilih pengguna untuk menambah saldo.</div>
        )}
      </div>
    </div>
  )
}

function UserBalance({ user, onChanged }: { user: UserSummary; onChanged: () => void }) {
  const [kind, setKind] = useState<EntryKind>('topup')
  const [direction, setDirection] = useState<Direction>('credit')
  const [amount, setAmount] = useState(0)
  const [note, setNote] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string>()
  const [done, setDone] = useState<EntryResult>()
  const [page, setPage] = useState(1)
  const ledger = useAsync(`${user.id}/ledger?page=${page}&after=${done?.entry_id ?? ''}`, () =>
    api<LedgerPage>(`/admin/users/${user.id}/ledger`, { query: { page } }),
  )

  const signed = kind === 'adjustment' && direction === 'debit' ? -amount : amount
  const noteMissing = kind === 'adjustment' && note.trim() === ''
  const canSubmit = amount > 0 && !noteMissing
  const actionLabel =
    kind === 'topup' ? 'Tambah saldo' : direction === 'credit' ? 'Tambah penyesuaian' : 'Kurangi saldo'

  async function submit() {
    setSubmitting(true)
    setError(undefined)
    try {
      const result = await api<EntryResult>(`/admin/users/${user.id}/adjustments`, {
        method: 'POST',
        body: { type: kind, amount_idr: signed, note: note.trim() || null },
      })
      setDone(result)
      setAmount(0)
      setNote('')
      setConfirming(false)
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Gagal menyimpan. Coba lagi.')
      setConfirming(false)
    } finally {
      setSubmitting(false)
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (canSubmit) setConfirming(true)
  }

  return (
    <section className="section" aria-labelledby="saldo-user">
      <div className="panel user-balance">
        <div className="user-balance__head">
          <div>
            <h2 id="saldo-user">{user.display_name}</h2>
            <p className="muted">{user.email}</p>
          </div>
          <p className="user-balance__figure num">{formatIDR(done?.user.balance_idr ?? user.balance_idr)}</p>
        </div>

        <form className="user-balance__form" onSubmit={onSubmit}>
          <div className="segmented" role="group" aria-label="Jenis entri">
            <button type="button" aria-pressed={kind === 'topup'} onClick={() => setKind('topup')}>
              Top-up
            </button>
            <button
              type="button"
              aria-pressed={kind === 'adjustment'}
              onClick={() => setKind('adjustment')}
            >
              Penyesuaian
            </button>
          </div>

          {kind === 'adjustment' && (
            <div className="segmented" role="group" aria-label="Arah penyesuaian">
              <button
                type="button"
                aria-pressed={direction === 'credit'}
                onClick={() => setDirection('credit')}
              >
                Tambah
              </button>
              <button
                type="button"
                aria-pressed={direction === 'debit'}
                onClick={() => setDirection('debit')}
              >
                Kurangi
              </button>
            </div>
          )}

          <label className="field">
            <span className="field__label">Nominal (Rupiah)</span>
            <input
              className="input input--amount"
              inputMode="numeric"
              autoComplete="off"
              placeholder="0"
              value={amount ? formatNumber(amount) : ''}
              onChange={(event) => {
                setAmount(parseDigits(event.target.value))
                setConfirming(false)
              }}
            />
          </label>

          <label className="field">
            <span className="field__label">
              {kind === 'adjustment' ? 'Alasan (wajib)' : 'Catatan (opsional)'}
            </span>
            <textarea
              className="input"
              maxLength={500}
              value={note}
              placeholder={kind === 'topup' ? 'Misalnya: QRIS 28 Sep, bukti via WA' : ''}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>

          {error && <p className="notice notice--error">{error}</p>}
          {done && !confirming && (
            <p className="notice notice--ok" role="status">
              Tersimpan. Saldo {done.user.display_name} sekarang{' '}
              <span className="num">{formatIDR(done.balance_after_idr)}</span>.
            </p>
          )}

          {confirming ? (
            <div className="confirm" role="alertdialog" aria-label="Konfirmasi">
              <p>
                {signed < 0 ? 'Kurangi' : 'Tambah'}{' '}
                <span className="num">{formatIDR(Math.abs(signed))}</span>{' '}
                {signed < 0 ? 'dari' : 'ke'} saldo {user.display_name}?
              </p>
              <div className="chips">
                <button
                  type="button"
                  className="button button--primary"
                  disabled={submitting}
                  onClick={() => void submit()}
                >
                  {submitting ? 'Menyimpan…' : `Ya, ${actionLabel.toLowerCase()}`}
                </button>
                <button type="button" className="button" onClick={() => setConfirming(false)}>
                  Batal
                </button>
              </div>
            </div>
          ) : (
            <p>
              <button type="submit" className="button button--primary" disabled={!canSubmit}>
                {actionLabel}
              </button>
            </p>
          )}
        </form>
      </div>

      <h3>Riwayat saldo</h3>
      {ledger.error && <p className="notice notice--error">{ledger.error.message}</p>}
      {ledger.data && (
        <LedgerTable
          items={ledger.data.items}
          page={ledger.data.page}
          pageSize={ledger.data.page_size}
          total={ledger.data.total}
          onPage={setPage}
          emptyText="Belum ada transaksi untuk pengguna ini."
        />
      )}
    </section>
  )
}
