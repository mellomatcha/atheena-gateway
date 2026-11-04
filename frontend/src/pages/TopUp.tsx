import { useState } from 'react'
import { api, type LedgerPage } from '../api'
import { LedgerTable } from '../components/LedgerTable'
import { formatIDR, formatNumber, parseDigits } from '../format'
import { useMe } from '../session-context'
import { useAsync } from '../useAsync'

const QUICK_AMOUNTS = [50_000, 100_000, 250_000, 500_000]

export function TopUpPage() {
  const { me } = useMe()
  const [amount, setAmount] = useState(0)
  const [method, setMethod] = useState('BCA')
  const [quote, setQuote] = useState<{ whatsapp_url: string; message: string } | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function prepare() {
    setBusy(true)
    setError('')
    setQuote(null)
    try {
      setQuote(await api('/topup/quote', { method: 'POST', body: { amount_idr: amount, method } }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Coba lagi sebentar.')
    } finally {
      setBusy(false)
    }
  }
  const [page, setPage] = useState(1)
  const [kind, setKind] = useState<'all' | 'credits'>('all')

  const ledger = useAsync(`ledger?page=${page}&kind=${kind}`, () =>
    api<LedgerPage>('/ledger', { query: { page, kind } }),
  )

  return (
    <div className="page">
      <header className="page__head">
        <h1>Top-up saldo</h1>
        <p className="muted">
          Pilih nominal dan metode pembayaran, lalu hubungi admin lewat WhatsApp.
        </p>
      </header>

      <section className="topup-manual" aria-label="Kalkulator top-up">
        <div>
          <h2>Isi saldo sesuai kebutuhan</h2>
          <label className="field">
            <span className="field__label">Nominal top-up (Rupiah)</span>
            <input
              className="input"
              inputMode="numeric"
              autoComplete="off"
              placeholder="50.000"
              value={amount ? formatNumber(amount) : ''}
              onChange={(e) => {
                setAmount(parseDigits(e.target.value))
                setQuote(null)
              }}
            />
          </label>
          <div className="chips" role="group" aria-label="Nominal cepat">
            {QUICK_AMOUNTS.map((value) => (
              <button
                className="chip"
                key={value}
                onClick={() => {
                  setAmount(value)
                  setQuote(null)
                }}
              >
                {formatIDR(value)}
              </button>
            ))}
          </div>
          <label className="field">
            <span className="field__label">Bayar lewat</span>
            <select
              className="input"
              value={method}
              onChange={(e) => {
                setMethod(e.target.value)
                setQuote(null)
              }}
            >
              <optgroup label="Transfer bank">
                {['BCA', 'Mandiri', 'BRI', 'BNI', 'BSI', 'Bank lainnya'].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </optgroup>
              <optgroup label="E-wallet">
                {['DANA', 'GoPay', 'OVO', 'ShopeePay', 'LinkAja', 'E-wallet lainnya'].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </optgroup>
            </select>
          </label>
          <p className="muted">
            Pilih metode yang ingin dipakai. Admin akan mengirim detail tujuan pembayaran lewat
            WhatsApp.
          </p>
        </div>
        <div className="topup-summary">
          <h2>Ringkasan top-up</h2>
          <p>
            Saldo saat ini <strong className="money">{formatIDR(me.balance_idr)}</strong>
          </p>
          <p>
            Nominal top-up <strong className="money">{formatIDR(amount)}</strong>
          </p>
          <p>
            Perkiraan saldo setelah konfirmasi{' '}
            <strong className="money">{formatIDR(me.balance_idr + amount)}</strong>
          </p>
          <p className="muted">
            Minimal Rp1.000, maksimal Rp100.000.000. Saldo masuk setelah pembayaran diverifikasi
            admin.
          </p>
          <button
            className="button button--primary"
            disabled={busy || amount < 1000 || amount > 100000000}
            onClick={prepare}
          >
            {busy ? 'Menyiapkan…' : 'Siapkan pesan WhatsApp'}
          </button>
          {error && (
            <p role="alert" className="notice notice--error">
              {error}
            </p>
          )}
          {quote && (
            <div>
              <pre className="topup-message">{quote.message}</pre>
              <a
                className="button button--primary"
                href={quote.whatsapp_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Lanjut ke WhatsApp
              </a>
              <p className="muted">
                Pesan berisi username, email akun, nominal, dan metode pilihanmu. Periksa lalu kirim
                di WhatsApp.
              </p>
            </div>
          )}
        </div>
      </section>

      <section className="section" aria-labelledby="riwayat">
        <div className="section__head">
          <h2 id="riwayat">Riwayat saldo</h2>
          <div className="segmented" role="group" aria-label="Filter riwayat">
            <button
              type="button"
              aria-pressed={kind === 'all'}
              onClick={() => {
                setKind('all')
                setPage(1)
              }}
            >
              Semua
            </button>
            <button
              type="button"
              aria-pressed={kind === 'credits'}
              onClick={() => {
                setKind('credits')
                setPage(1)
              }}
            >
              Top-up dan penyesuaian
            </button>
          </div>
        </div>
        {ledger.error && <p className="notice notice--error">{ledger.error.message}</p>}
        {ledger.data && (
          <LedgerTable
            items={ledger.data.items}
            page={ledger.data.page}
            pageSize={ledger.data.page_size}
            total={ledger.data.total}
            onPage={setPage}
            emptyText="Belum ada transaksi. Top-up pertama Anda akan muncul di sini."
          />
        )}
      </section>
    </div>
  )
}
