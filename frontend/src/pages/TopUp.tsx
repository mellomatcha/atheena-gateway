import { useState } from 'react'
import { api, type LedgerPage } from '../api'
import { LedgerTable } from '../components/LedgerTable'
import { formatNumber, parseDigits } from '../format'
import { useMe } from '../session-context'
import { useAsync } from '../useAsync'
import { whatsappLink } from '../whatsapp'

interface TopupInfo {
  whatsapp_number: string
  qris_image_path: string
}

const QUICK_AMOUNTS = [50_000, 100_000, 250_000, 500_000]

export function TopUpPage() {
  const { me } = useMe()
  const [amount, setAmount] = useState(0)
  const [qrisMissing, setQrisMissing] = useState(false)
  const [page, setPage] = useState(1)
  const [kind, setKind] = useState<'all' | 'credits'>('all')

  const info = useAsync('topup-info', () => api<TopupInfo>('/topup-info'))
  const ledger = useAsync(`ledger?page=${page}&kind=${kind}`, () =>
    api<LedgerPage>('/ledger', { query: { page, kind } }),
  )

  const link = info.data
    ? whatsappLink(info.data.whatsapp_number, me.display_name, me.email, amount)
    : undefined

  return (
    <div className="page">
      <header className="page__head">
        <h1>Top-up saldo</h1>
        <p className="muted">
          Bayar lewat QRIS, lalu kirim bukti ke admin lewat WhatsApp. Saldo bertambah setelah admin
          memeriksa pembayaran.
        </p>
      </header>

      <section className="topup" aria-label="Cara top-up">
        <figure className="topup__qris">
          {qrisMissing || !info.data ? (
            <div className="topup__qris-missing muted">
              {info.error ? info.error.message : 'Gambar QRIS belum tersedia. Hubungi admin.'}
            </div>
          ) : (
            <img
              src={info.data.qris_image_path}
              alt="Kode QRIS untuk pembayaran top-up Atheena"
              onError={() => setQrisMissing(true)}
            />
          )}
        </figure>

        <ol className="steps">
          <li className="step">
            <h2>Bayar lewat QRIS</h2>
            <p className="muted">
              Pindai kode dengan aplikasi bank atau e-wallet, lalu bayar nominal yang Anda inginkan.
              Simpan bukti pembayarannya.
            </p>
          </li>
          <li className="step">
            <h2>Tulis nominal yang dibayar</h2>
            <label className="field">
              <span className="field__label">Nominal (Rupiah)</span>
              <input
                className="input input--amount"
                inputMode="numeric"
                autoComplete="off"
                placeholder="0"
                value={amount ? formatNumber(amount) : ''}
                onChange={(event) => setAmount(parseDigits(event.target.value))}
              />
            </label>
            <div className="chips" role="group" aria-label="Nominal cepat">
              {QUICK_AMOUNTS.map((value) => (
                <button key={value} type="button" className="chip" onClick={() => setAmount(value)}>
                  {formatNumber(value)}
                </button>
              ))}
            </div>
          </li>
          <li className="step">
            <h2>Kirim bukti ke admin</h2>
            <p className="muted">
              WhatsApp terbuka dengan pesan berisi nama, email, dan nominal Anda. Lampirkan bukti
              pembayaran sebelum mengirim.
            </p>
            <p>
              <a
                className="button button--primary"
                href={amount > 0 && link ? link : undefined}
                target="_blank"
                rel="noopener noreferrer"
                aria-disabled={amount <= 0 || !link}
                onClick={(event) => {
                  if (amount <= 0 || !link) event.preventDefault()
                }}
              >
                Konfirmasi via WhatsApp
              </a>
            </p>
            {amount <= 0 && <p className="field__label">Isi nominal dulu untuk mengaktifkan tombol.</p>}
          </li>
        </ol>
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
