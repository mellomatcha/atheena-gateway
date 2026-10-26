import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { ThemeToggle } from '../components/ThemeToggle'
import { formatIDR, formatNumber } from '../format'
import { useAsync } from '../useAsync'
import { siteLinks } from '../sites'

interface CatalogModel {
  id: string
  name: string
  provider: string
  multiplier: string
  context_window: number | null
  gateway_listed: boolean
  inference_verified: boolean
  supports_images: boolean
}
interface Plan {
  id: string
  name: string
  days: number
  tokens: number
  price_idr: number
  regular_idr: number
}
interface Catalog {
  models: CatalogModel[]
  plans: Plan[]
  captured_at: string
  version: string
}
interface Quote {
  model: string
  plan: string
  price_idr: number
  regular_idr: number
  included_tokens: number
  effective_idr_per_million: string
  method: string
}
async function publicGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api/public/${path}`, { headers: { Accept: 'application/json' } })
  if (!response.ok) throw new Error('Data harga belum dapat dimuat. Coba lagi sebentar.')
  return response.json() as Promise<T>
}

const factorLabel = (value: string | undefined) =>
  value === undefined ? '…' : Number(value).toLocaleString('id-ID', { maximumFractionDigits: 2 })

export function PricingPage({ workspace = false }: { workspace?: boolean }) {
  const links = siteLinks()
  const catalog = useAsync('public-catalog', () => publicGet<Catalog>('catalog'))
  const [params] = useSearchParams()
  const [selectedModel, setModelId] = useState(params.get('model') ?? 'deepseek-v4.1-flash')
  const modelId =
    catalog.data && !catalog.data.models.some((m) => m.id === selectedModel)
      ? 'deepseek-v4.1-flash'
      : selectedModel
  const [period, setPeriod] = useState('monthly')
  const [tokensM, setTokensM] = useState('100')
  const [promo, setPromo] = useState(true)
  const [provider, setProvider] = useState('Semua')
  const [query, setQuery] = useState('')
  const quotes = useAsync(`quotes:${modelId}:${promo}`, () =>
    Promise.all(
      ['daily', 'weekly', 'monthly'].map((plan) =>
        publicGet<Quote>(`quote?model=${encodeURIComponent(modelId)}&plan=${plan}&promo=${promo}`),
      ),
    ),
  )
  const model = catalog.data?.models.find((m) => m.id === modelId)
  const currentQuotes =
    quotes.loading || quotes.error ? undefined : quotes.data?.filter((q) => q.model === modelId)
  const choice = currentQuotes?.find((q) => q.plan === period)
  const target = Number(tokensM)
  const validTarget =
    tokensM.trim() !== '' && Number.isFinite(target) && target > 0 && target <= 1000000
  const packs = choice && validTarget ? Math.ceil((target * 1e6) / choice.included_tokens) : 0
  const models =
    catalog.data?.models.filter(
      (m) =>
        (provider === 'Semua' || m.provider === provider) &&
        `${m.name} ${m.id}`.toLowerCase().includes(query.toLowerCase()),
    ) ?? []

  return (
    <div className={workspace ? 'page pricing pricing--workspace' : 'pricing pricing--public'}>
      {!workspace && (
        <header className="pricing-nav">
          <a className="wordmark" href="/">
            <img src="/brand/mark.svg" width="28" height="30" alt="" /> ATHEENA
          </a>
          <a href="/#models">Model</a>
          <ThemeToggle />
          <a className="button" href={links.dashboard}>
            Masuk ↗
          </a>
        </header>
      )}
      <header className="pricing-hero">
        <div>
          <span className="eyebrow">ATHEENA / PILIH KAPASITASMU</span>
          <h1>
            Ruang untuk
            <br />
            <em>ambisimu.</em>
          </h1>
        </div>
        <div className="pricing-hero__aside">
          <span className="pricing-symbol" aria-hidden="true">
            ✳
          </span>
          <p>
            Dari satu ide sampai proyek berikutnya.
            <br />
            Pilih model. Tentukan ritmemu.
          </p>
          <a href="#calculator">Hitung kebutuhanmu ↓</a>
        </div>
      </header>
      <p className="draft-notice">
        <span className="status-dot" />
        Harga dalam rupiah · Pilih paket dan hitung kebutuhanmu. Pembelian segera tersedia.
      </p>
      {catalog.error && (
        <p className="notice notice--error" role="alert">
          {catalog.error.message}{' '}
          <button className="button" onClick={catalog.reload}>
            Coba lagi
          </button>
        </p>
      )}
      {catalog.loading && <p role="status">Memuat katalog model…</p>}
      {catalog.data && (
        <>
          <section className="plan-selection" aria-labelledby="plans-title">
            <div className="section__head">
              <div>
                <span className="eyebrow">01 / PILIH PAKET</span>
                <h2 id="plans-title">Sesuai ritme kerjamu.</h2>
              </div>
              <label className="field model-picker">
                <span className="field__label">Model untuk simulasi harga</span>
                <select
                  className="input"
                  value={modelId}
                  onChange={(e) => setModelId(e.target.value)}
                >
                  {catalog.data.models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} · {factorLabel(m.multiplier)}×
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="pricing-options">
              <span className="muted">
                {model?.name} · multiplier ATHEENA {factorLabel(model?.multiplier)}×
              </span>
              <label className="check">
                <input
                  type="checkbox"
                  checked={promo}
                  onChange={(e) => setPromo(e.target.checked)}
                />
                Tampilkan promo bulanan
              </label>
            </div>
            {quotes.error && (
              <p role="alert" className="notice notice--error">
                {quotes.error.message}
              </p>
            )}
            <div className="plan-grid">
              {catalog.data.plans.map((p, i) => {
                const q = currentQuotes?.find((x) => x.plan === p.id)
                return (
                  <article
                    key={p.id}
                    className={`plan-card ${period === p.id ? 'plan-card--selected' : ''}`}
                  >
                    <div className="plan-card__top">
                      <span className="mono">
                        0{i + 1} / {p.days} HARI
                      </span>
                      {p.id === 'monthly' && <span className="plan-tag">Jangka panjang</span>}
                    </div>
                    <h3>{p.name}</h3>
                    <p className="plan-model">{model?.name}</p>
                    <div className="plan-price" aria-live="polite">
                      {q && !quotes.loading ? (
                        <>
                          <strong>{formatIDR(q.price_idr)}</strong>
                          <span>
                            / {p.days === 1 ? 'hari' : p.days === 7 ? '7 hari' : '30 hari'}
                          </span>
                        </>
                      ) : (
                        <strong>…</strong>
                      )}
                    </div>
                    <p className="plan-promo">
                      {q && !quotes.loading && q.regular_idr > q.price_idr ? (
                        <>
                          <s>{formatIDR(q.regular_idr)}</s>
                          <span>Harga promo</span>
                        </>
                      ) : (
                        'Satu kali pembayaran, tanpa perpanjangan otomatis.'
                      )}
                    </p>
                    <div className="plan-quota">
                      <strong>
                        {p.tokens / 1e6}
                        <span> juta</span>
                      </strong>
                      <span>token per periode</span>
                    </div>
                    <ul>
                      <li>Total input + output, termasuk token cache</li>
                      <li>Berlaku {p.days} hari sejak aktivasi</li>
                      <li>API key pribadi & riwayat pemakaian</li>
                      <li>Untuk model yang dipilih</li>
                    </ul>
                    <button
                      className={`button ${period === p.id ? 'button--primary' : ''}`}
                      aria-pressed={period === p.id}
                      onClick={() => setPeriod(p.id)}
                    >
                      {period === p.id ? 'Paket dipilih ✓' : `Simulasikan ${p.name.toLowerCase()}`}
                      <span aria-hidden="true">↗</span>
                    </button>
                  </article>
                )
              })}
            </div>
            <p className="pricing-explainer">
              DeepSeek V4.1 Flash, GLM 5.3, HY4, GPT 5.6 Luna, dan Gemini 3.5 Flash memakai harga
              dasar 1×. Model lainnya mengikuti rasio multiplier provider terhadap GLM 5.3 (0,79×);
              rasio di bawah 1× menjadi 0,45×. Harga dibulatkan ke atas per Rp100.
            </p>
          </section>
          <section className="calculator" id="calculator" aria-labelledby="calculator-title">
            <div className="calculator-copy">
              <span className="eyebrow">02 / KALKULATOR</span>
              <h2 id="calculator-title">
                Rencanakan.
                <br />
                <em>Lalu berkarya.</em>
              </h2>
              <p>Bandingkan kebutuhan token dengan kapasitas paket pilihanmu.</p>
              <label className="field">
                <span className="field__label">Perkiraan total token (juta)</span>
                <input
                  className="input"
                  type="number"
                  min="0.001"
                  max="1000000"
                  step="any"
                  value={tokensM}
                  onChange={(e) => setTokensM(e.target.value)}
                />
              </label>
              {!validTarget && (
                <p className="notice notice--error">
                  Masukkan jumlah lebih dari 0, maksimal 1.000.000 juta token.
                </p>
              )}
            </div>
            <div className="calculator-result" aria-live="polite">
              <p className="eyebrow">ESTIMASI KEBUTUHAN PAKET</p>
              <p className="result-price money">
                {choice && validTarget && !quotes.loading && !quotes.error
                  ? formatIDR(choice.price_idr * packs)
                  : '—'}
              </p>
              <p>
                {packs
                  ? `${packs} paket ${catalog.data.plans.find((p) => p.id === period)?.name.toLowerCase()} untuk ${formatNumber(target)} juta token`
                  : 'Masukkan kebutuhan tokenmu.'}
              </p>
              <dl>
                <div>
                  <dt>Kapasitas per paket</dt>
                  <dd>{choice ? `${choice.included_tokens / 1e6} juta token` : '—'}</dd>
                </div>
                <div>
                  <dt>Harga efektif per 1 juta</dt>
                  <dd className="money">
                    {choice && !quotes.loading
                      ? formatIDR(Number(choice.effective_idr_per_million))
                      : '—'}
                  </dd>
                </div>
                <div>
                  <dt>Multiplier ATHEENA</dt>
                  <dd>{factorLabel(model?.multiplier)}×</dd>
                </div>
              </dl>
              <p className="muted">
                Perhitungan membulatkan ke paket penuh. Belum termasuk konversi antar-model; masa
                aktif paket tidak otomatis bertambah.
              </p>
              <button className="button" disabled>
                Pembelian segera tersedia
              </button>
            </div>
          </section>
          <section className="pricing-catalog" aria-labelledby="catalog-title">
            <div className="section__head">
              <div>
                <span className="eyebrow">03 / KATALOG MODEL</span>
                <h2 id="catalog-title">Banyak perspektif. Satu gerbang.</h2>
              </div>
              <p className="muted">
                {catalog.data.models.length} model dari CB CLI {catalog.data.version}
              </p>
            </div>
            <div className="catalog-filters">
              <div role="group" aria-label="Filter provider">
                {['Semua', ...new Set(catalog.data.models.map((m) => m.provider))].map((p) => (
                  <button
                    className="button"
                    key={p}
                    aria-pressed={provider === p}
                    onClick={() => setProvider(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
              <input
                className="input"
                aria-label="Cari model"
                placeholder="Cari model…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div className="model-grid">
              {models.map((m) => (
                <button
                  key={m.id}
                  className={`model-card ${m.id === modelId ? 'model-card--selected' : ''}`}
                  onClick={() => setModelId(m.id)}
                  aria-pressed={m.id === modelId}
                >
                  <span className="model-monogram" aria-hidden="true">
                    {m.provider === 'DeepSeek' ? 'DS' : m.provider.slice(0, 2).toUpperCase()}
                  </span>
                  <span>
                    <strong>{m.name}</strong>
                    <small>
                      {m.provider} ·{' '}
                      {m.context_window
                        ? `${formatNumber(m.context_window / 1000)}K konteks`
                        : 'Konteks bervariasi'}
                    </small>
                    <small>
                      {m.inference_verified
                        ? 'Respons terverifikasi'
                        : m.gateway_listed
                          ? 'Terdaftar di gateway'
                          : 'Katalog provider · belum diverifikasi'}
                    </small>
                  </span>
                  <span className="multiplier">{factorLabel(m.multiplier)}×</span>
                </button>
              ))}
            </div>
            {models.length === 0 && <p className="notice">Tidak ada model yang cocok.</p>}
            <p className="catalog-source">
              Snapshot model {new Date(catalog.data.captured_at).toLocaleDateString('id-ID')} ·
              Angka di atas adalah multiplier harga jual ATHEENA. Ketersediaan mengikuti provider.
            </p>
          </section>
        </>
      )}
      {!workspace && (
        <footer className="pricing-footer">
          <div>
            <a className="wordmark" href="/">
              ATHEENA ✳
            </a>
            <p>Tegas berpikir. Bijak bertindak.</p>
          </div>
          <nav aria-label="Navigasi footer">
            <a href="/#filosofi">Filosofi</a>
            <a href="/#models">Model</a>
            <a href="/#mulai">Integrasi</a>
            <a href={links.dashboard}>Portal ↗</a>
          </nav>
          <small>© 2026 ATHEENA · Independent AI gateway</small>
        </footer>
      )}
    </div>
  )
}
