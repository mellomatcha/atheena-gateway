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
}
interface Plan {
  id: string
  name: string
  days: number
}
interface Offer {
  model: string
  plan: string
  days: number
  price_idr: number
  regular_idr: number
  included_tokens: number
  bonus_tokens: number
  bonus_models: string[]
  bonus_pool: string | null
  method: string
}
interface Catalog {
  models: CatalogModel[]
  plans: Plan[]
  offers: Offer[]
  captured_at: string
  version: string
}
async function publicGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api/public/${path}`, { headers: { Accept: 'application/json' } })
  if (!response.ok) throw new Error('Data harga belum dapat dimuat. Coba lagi sebentar.')
  return response.json() as Promise<T>
}
const factorLabel = (value: string | undefined) =>
  value === undefined ? '…' : Number(value).toLocaleString('id-ID', { maximumFractionDigits: 2 })
const chinaProviders = ['Tencent', 'Z.ai', 'Moonshot', 'DeepSeek']
const gptOrder = ['gpt-5.6-sol', 'gpt-6-astra', 'gpt-5.6-luna']

export function PricingPage({ workspace = false }: { workspace?: boolean }) {
  const links = siteLinks()
  const catalog = useAsync('public-catalog', () => publicGet<Catalog>('catalog'))
  const [params] = useSearchParams()
  const [selectedModel, setModelId] = useState(params.get('model') ?? '')
  const [calculatorModel, setCalculatorModel] = useState(
    params.get('model') ?? 'deepseek-v4.1-flash',
  )
  const filterId = catalog.data?.models.some((m) => m.id === selectedModel) ? selectedModel : ''
  const modelId = catalog.data?.models.some((m) => m.id === calculatorModel)
    ? calculatorModel
    : 'deepseek-v4.1-flash'
  const [period, setPeriod] = useState('monthly')
  const [tokensM, setTokensM] = useState('100')
  const [promo, setPromo] = useState(true)
  const [provider, setProvider] = useState('Semua')
  const [query, setQuery] = useState('')
  const offers = (catalog.data?.offers ?? []).map((offer) => ({
    ...offer,
    price_idr: promo ? offer.price_idr : offer.regular_idr,
  }))
  const model = catalog.data?.models.find((m) => m.id === modelId)
  const modelOffers = offers.filter((offer) => offer.model === modelId)
  const activePeriod = modelOffers.some((offer) => offer.plan === period) ? period : 'weekly'
  const choice = modelOffers.find((offer) => offer.plan === activePeriod)
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
  const remaining = (catalog.data?.models ?? []).filter((m) => m.id !== filterId)
  const sections = [
    {
      id: 'highlight',
      label: 'HIGHLIGHT',
      title: 'DeepSeek. Siap untuk setiap hari.',
      description: 'Satu model, tiga ritme. Pilih kapasitas yang pas untuk pekerjaanmu.',
      models: remaining.filter((m) => m.id === 'deepseek-v4.1-flash'),
    },
    {
      id: 'gpt',
      label: 'GPT',
      title: 'GPT. Pilih tenaga berpikirmu.',
      description: 'Sol dan Astra punya paket khusus. Pilihan GPT lainnya tersedia hingga bulanan.',
      models: remaining
        .filter((m) => m.provider === 'OpenAI')
        .sort(
          (a, b) =>
            (gptOrder.includes(a.id) ? gptOrder.indexOf(a.id) : 99) -
            (gptOrder.includes(b.id) ? gptOrder.indexOf(b.id) : 99),
        ),
    },
    {
      id: 'china',
      label: 'MODEL CHINA',
      title: 'Perspektif baru. Banyak kemungkinan.',
      description: 'GLM, HY, dan Kimi. Temukan model yang cocok dengan caramu bekerja.',
      models: remaining.filter(
        (m) => chinaProviders.includes(m.provider) && m.id !== 'deepseek-v4.1-flash',
      ),
    },
    {
      id: 'others',
      label: 'MODEL LAINNYA',
      title: 'Gemini dan pilihan lainnya.',
      description: 'Lengkapi perangkat kerjamu dengan pilihan model lainnya.',
      models: remaining.filter(
        (m) => m.provider !== 'OpenAI' && !chinaProviders.includes(m.provider),
      ),
    },
  ]
  function selectModel(id: string) {
    setModelId(id)
    if (id) setCalculatorModel(id)
  }
  function renderModel(m: CatalogModel) {
    return (
      <div className="model-offers" key={m.id} id={`model-${m.id}`}>
        <div className="model-offers__head">
          <div>
            <span className="eyebrow">{m.provider}</span>
            <h3>{m.name}</h3>
          </div>
          <span className="model-offers__rate">
            {offers.some((o) => o.model === m.id && o.method === 'fixed-model-package')
              ? 'Harga paket khusus'
              : `${factorLabel(m.multiplier)}× · harga ATHEENA`}
          </span>
        </div>
        <div
          className={`plan-grid ${offers.filter((o) => o.model === m.id).length === 2 ? 'plan-grid--pair' : ''}`}
        >
          {offers
            .filter((q) => q.model === m.id)
            .map((q) => {
              const p = catalog.data!.plans.find((plan) => plan.id === q.plan)!
              const selected = modelId === m.id && activePeriod === p.id
              return (
                <article
                  key={p.id}
                  aria-label={`${m.name} ${p.name}`}
                  className={`plan-card ${selected ? 'plan-card--selected' : ''} ${q.bonus_tokens ? 'plan-card--bonus' : ''}`}
                >
                  {q.bonus_tokens > 0 && (
                    <div className="plan-bonus-banner">BONUS 50 JT · LUNA / DEEPSEEK</div>
                  )}
                  <div className="plan-card__top">
                    <span className="mono">{q.days} HARI</span>
                    {q.regular_idr > q.price_idr && <span className="plan-tag">Promo bulanan</span>}
                  </div>
                  <h4>{p.name}</h4>
                  <p className="plan-model">{m.name}</p>
                  <div className="plan-price">
                    <strong>{formatIDR(q.price_idr)}</strong>
                    <span>/ {q.days === 1 ? 'hari' : `${q.days} hari`}</span>
                  </div>
                  <p className="plan-promo">
                    {q.regular_idr > q.price_idr ? (
                      <>
                        <s>{formatIDR(q.regular_idr)}</s>
                        <span>Harga promo</span>
                      </>
                    ) : (
                      'Sekali bayar, tanpa perpanjangan otomatis.'
                    )}
                  </p>
                  <div className="plan-quota">
                    <strong>
                      {q.included_tokens / 1e6}
                      <span> juta</span>
                    </strong>
                    <span>token {q.bonus_tokens ? 'utama' : 'per periode'}</span>
                  </div>
                  {q.bonus_tokens > 0 && (
                    <div className="plan-bonus-detail">
                      <strong>+50 juta token gratis</strong>
                      <span>
                        Satu kuota gabungan untuk GPT 5.6 Luna & DeepSeek V4.1 Flash. Berlaku 7
                        hari.
                      </span>
                    </div>
                  )}
                  <ul>
                    <li>Total input + output, termasuk token cache</li>
                    <li>Berlaku {q.days} hari sejak aktivasi</li>
                    <li>API key pribadi & riwayat pemakaian</li>
                    <li>
                      {m.inference_verified
                        ? 'Respons model terverifikasi'
                        : 'Ketersediaan model mengikuti provider'}
                    </li>
                  </ul>
                  <button
                    className={`button ${selected ? 'button--primary' : ''}`}
                    aria-label={`${m.name}: Simulasikan ${p.name.toLowerCase()}`}
                    aria-pressed={selected}
                    onClick={() => {
                      setCalculatorModel(m.id)
                      setPeriod(p.id)
                      document.getElementById('calculator')?.scrollIntoView?.({ block: 'start' })
                    }}
                  >
                    {selected ? 'Paket dipilih ✓' : `Simulasikan ${p.name.toLowerCase()}`}
                    <span aria-hidden="true">↗</span>
                  </button>
                </article>
              )
            })}
        </div>
      </div>
    )
  }
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
            Ruang untuk{' '}
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
                <span className="field__label">Tampilkan model di atas</span>
                <select
                  className="input"
                  value={filterId}
                  onChange={(e) => selectModel(e.target.value)}
                >
                  <option value="">Semua model</option>
                  {catalog.data.models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="pricing-options">
              <span className="muted">
                Semua paket bisa dibandingkan. Pilih model untuk menaruhnya paling atas.
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
            <aside className="weekly-promo">
              <span className="eyebrow">LEBIH BANYAK RUANG BERKARYA</span>
              <strong>Sol & Astra mingguan: bonus 50 juta token.</strong>
              <p>
                50 juta token model utama + 50 juta token gabungan GPT 5.6 Luna / DeepSeek V4.1
                Flash, tanpa biaya tambahan.
              </p>
              <a href="#model-gpt-5.6-sol">Lihat paket GPT ↓</a>
            </aside>
            {filterId && (
              <section
                className="offer-section offer-section--pinned"
                aria-labelledby="selected-model-title"
              >
                <span className="eyebrow">PILIHANMU</span>
                <h2 id="selected-model-title">
                  Paket {catalog.data.models.find((m) => m.id === filterId)!.name}
                </h2>
                {renderModel(catalog.data.models.find((m) => m.id === filterId)!)}
              </section>
            )}
            {filterId && <h2 className="recommendations-title">Mungkin kamu tertarik.</h2>}
            {sections
              .filter((s) => s.models.length > 0)
              .map((s) => (
                <section
                  className={`offer-section offer-section--${s.id}`}
                  key={s.id}
                  aria-labelledby={`section-${s.id}`}
                >
                  <div className="offer-section__title">
                    <span className="eyebrow">{s.label}</span>
                    <h2 id={`section-${s.id}`}>{s.title}</h2>
                    <p className="muted">{s.description}</p>
                  </div>
                  {s.models.map(renderModel)}
                </section>
              ))}
            <p className="pricing-explainer">
              Model dengan multiplier 1× memakai harga dan kuota dasar DeepSeek sampai paket
              bulanan. Sol dan Astra memakai harga paket khusus di atas.
            </p>
          </section>
          <section className="calculator" id="calculator" aria-labelledby="calculator-title">
            <div className="calculator-copy">
              <span className="eyebrow">02 / KALKULATOR</span>
              <h2 id="calculator-title">
                Rencanakan.{' '}
                <br />
                <em>Lalu berkarya.</em>
              </h2>
              <p>Bandingkan kebutuhan token dengan kapasitas paket pilihanmu.</p>
              <label className="field">
                <span className="field__label">Model kalkulator</span>
                <select
                  className="input"
                  value={modelId}
                  onChange={(e) => setCalculatorModel(e.target.value)}
                >
                  {catalog.data.models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field__label">Periode paket</span>
                <select
                  className="input"
                  value={activePeriod}
                  onChange={(e) => setPeriod(e.target.value)}
                >
                  {modelOffers.map((q) => (
                    <option key={q.plan} value={q.plan}>
                      {catalog.data!.plans.find((p) => p.id === q.plan)!.name}
                    </option>
                  ))}
                </select>
              </label>
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
                {choice && validTarget ? formatIDR(choice.price_idr * packs) : '—'}
              </p>
              <p>
                {packs
                  ? `${packs} paket ${catalog.data.plans.find((p) => p.id === activePeriod)?.name.toLowerCase()} untuk ${formatNumber(target)} juta token ${model?.name}`
                  : 'Masukkan kebutuhan tokenmu.'}
              </p>
              <dl>
                <div>
                  <dt>Token utama per paket</dt>
                  <dd>{choice ? `${choice.included_tokens / 1e6} juta token` : '—'}</dd>
                </div>
                <div>
                  <dt>Harga efektif per 1 juta token utama</dt>
                  <dd className="money">
                    {choice ? formatIDR(choice.price_idr / (choice.included_tokens / 1e6)) : '—'}
                  </dd>
                </div>
                <div>
                  <dt>Dasar harga</dt>
                  <dd>
                    {choice?.method === 'fixed-model-package'
                      ? 'Paket khusus'
                      : `${factorLabel(model?.multiplier)}×`}
                  </dd>
                </div>
                {choice && choice.bonus_tokens > 0 && (
                  <div>
                    <dt>Bonus gabungan per paket</dt>
                    <dd>50 juta · Luna / DeepSeek</dd>
                  </div>
                )}
              </dl>
              {choice && choice.bonus_tokens > 0 && (
                <p className="calculator-bonus">
                  Bonus terpisah dari kuota {model?.name}; tidak menambah token model utama.{' '}
                  {packs > 0 &&
                    `Total bonus: ${formatNumber((packs * choice.bonus_tokens) / 1e6)} juta token.`}
                </p>
              )}
              <p className="muted">
                Perhitungan membulatkan ke paket penuh. Masa aktif paket tidak otomatis bertambah.
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
              <p className="muted">{catalog.data.models.length} model pilihan</p>
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
                  className={`model-card ${m.id === filterId ? 'model-card--selected' : ''}`}
                  onClick={() => selectModel(m.id)}
                  aria-pressed={m.id === filterId}
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
                  <span className="multiplier">
                    {offers.some((o) => o.model === m.id && o.method === 'fixed-model-package')
                      ? 'Khusus'
                      : `${factorLabel(m.multiplier)}×`}
                  </span>
                </button>
              ))}
            </div>
            {models.length === 0 && <p className="notice">Tidak ada model yang cocok.</p>}
            <p className="catalog-source">
              Snapshot model {new Date(catalog.data.captured_at).toLocaleDateString('id-ID')} ·
              Ketersediaan mengikuti provider.
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
