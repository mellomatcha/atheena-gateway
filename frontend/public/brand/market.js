// Public model metadata only. Provider credentials never enter this page.
const grid = document.querySelector('[data-model-grid]')
const status = document.querySelector('[data-catalog-status]')
const filters = document.querySelector('[data-provider-filters]')
const motion = document.querySelector('[data-motion-control]')
motion.addEventListener('click', () => {
  const paused = document.documentElement.classList.toggle('motion-paused')
  motion.setAttribute('aria-pressed', String(paused))
  motion.textContent = paused ? 'Lanjut animasi' : 'Jeda animasi'
})
function element(tag, text, className) {
  const node = document.createElement(tag)
  if (text) node.textContent = text
  if (className) node.className = className
  return node
}
async function loadCatalog() {
  try {
    const response = await fetch('/api/public/catalog', { headers: { Accept: 'application/json' } })
    if (!response.ok) throw new Error('Catalog unavailable')
    const catalog = await response.json()
    function render(provider) {
      grid.replaceChildren()
      const models = catalog.models.filter(
        (model) => provider === 'Semua' || model.provider === provider,
      )
      status.textContent = `${models.length} model · ${provider === 'Semua' ? 'Semua provider' : provider}`
      for (const model of models) {
        const card = element('a', '', 'market-model')
        card.href = `/pricing?model=${encodeURIComponent(model.id)}`
        const icon = element(
          'span',
          model.provider === 'DeepSeek' ? 'DS' : model.provider.slice(0, 2).toUpperCase(),
          'market-icon',
        )
        icon.setAttribute('aria-hidden', 'true')
        const info = element('span')
        info.append(element('strong', model.name), element('small', model.provider))
        info.append(
          element(
            'small',
            model.inference_verified
              ? 'Respons terverifikasi'
              : model.gateway_listed
                ? 'Terdaftar di gateway'
                : 'Katalog provider · belum diverifikasi',
          ),
        )
        const factor = Number(model.multiplier).toLocaleString('id-ID', {
          maximumFractionDigits: 2,
        })
        const fixed = model.pricing_method === 'fixed-model-package'
        const multiplier = element('span', fixed ? 'Khusus' : `${factor}×`, 'market-multiplier')
        multiplier.setAttribute(
          'aria-label',
          fixed ? 'Harga paket khusus' : `Multiplier ATHEENA ${factor}`,
        )
        card.append(icon, info, multiplier)
        grid.append(card)
      }
      for (const button of filters.children)
        button.setAttribute('aria-pressed', String(button.textContent === provider))
    }
    for (const provider of ['Semua', ...new Set(catalog.models.map((model) => model.provider))]) {
      const button = element('button', provider)
      button.addEventListener('click', () => render(provider))
      filters.append(button)
    }
    const date = new Date(catalog.captured_at).toLocaleDateString('id-ID')
    document.querySelector('[data-catalog-source]').textContent =
      `CB CLI ${catalog.version} · Snapshot ${date}. Multiplier harga jual ATHEENA; ketersediaan model mengikuti provider.`
    render('Semua')
  } catch {
    status.textContent = 'Katalog belum dapat dimuat. '
    const retry = element('button', 'Coba lagi', 'motion-control')
    retry.addEventListener('click', () => {
      status.textContent = 'Memuat katalog…'
      loadCatalog()
    })
    status.append(retry)
  }
}
loadCatalog()
