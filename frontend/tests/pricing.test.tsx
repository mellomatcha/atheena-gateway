import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { PricingPage } from '../src/pages/Pricing'
import { ThemeToggle } from '../src/components/ThemeToggle'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  localStorage.clear()
})
const models = [
  {
    id: 'deepseek-v4.1-flash',
    name: 'DeepSeek V4.1 Flash',
    provider: 'DeepSeek',
    multiplier: '1',
    inference_verified: true,
  },
  {
    id: 'glm-5.3-flash',
    name: 'GLM 5.3 Flash',
    provider: 'Z.ai',
    multiplier: '0.45',
    inference_verified: true,
  },
  { id: 'gpt-5.6-sol', name: 'GPT 5.6 Sol', provider: 'OpenAI', multiplier: '4.39' },
  { id: 'gpt-6-astra', name: 'GPT 6 Astra', provider: 'OpenAI', multiplier: '8.44' },
  { id: 'gpt-5.6-luna', name: 'GPT 5.6 Luna', provider: 'OpenAI', multiplier: '1' },
  { id: 'gemini-3.5-flash', name: 'Gemini 3.5 Flash', provider: 'Google', multiplier: '1' },
]
const plans = [
  { id: 'daily', name: 'Harian', days: 1 },
  { id: 'weekly', name: 'Mingguan', days: 7 },
  { id: 'monthly', name: 'Bulanan', days: 30 },
]
const offers = models.flatMap((model) => {
  const custom = ['gpt-5.6-sol', 'gpt-6-astra'].includes(model.id)
  return plans
    .filter((p) => !custom || p.id !== 'monthly')
    .map((plan, i) => {
      const price =
        model.id === 'gpt-5.6-sol'
          ? [30000, 54900][i]
          : model.id === 'gpt-6-astra'
            ? [39000, 64900][i]
            : model.id === 'glm-5.3-flash'
              ? [4500, 15800, 22500][i]
              : [9900, 34900, 49900][i]
      const bonus = custom && plan.id === 'weekly'
      return {
        model: model.id,
        plan: plan.id,
        days: plan.days,
        price_idr: price,
        regular_idr: plan.id === 'monthly' ? (model.id === 'glm-5.3-flash' ? 27000 : 59900) : price,
        included_tokens: custom ? 50000000 : [100000000, 250000000, 500000000][i],
        bonus_tokens: bonus ? 50000000 : 0,
        bonus_models: bonus ? ['gpt-5.6-luna', 'deepseek-v4.1-flash'] : [],
        bonus_pool: bonus ? 'shared' : null,
        method: custom ? 'fixed-model-package' : 'atheena-retail-factor',
      }
    })
})
function mockCatalog() {
  const fetcher = vi.fn(() =>
    Promise.resolve(
      new Response(
        JSON.stringify({
          models,
          plans,
          offers,
          version: '2.173.0',
          captured_at: '2026-10-23T00:00:00Z',
        }),
        { status: 200 },
      ),
    ),
  )
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}
function renderPricing(path = '/pricing') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <PricingPage />
    </MemoryRouter>,
  )
}

test('default shows all packages in ordered model sections without a session', async () => {
  const fetcher = mockCatalog()
  renderPricing()
  const highlight = await screen.findByRole('region', { name: 'DeepSeek. Siap untuk setiap hari.' })
  expect(within(highlight).getAllByRole('article')).toHaveLength(3)
  expect(screen.getAllByRole('article')).toHaveLength(16)
  expect(
    (screen.getByRole('combobox', { name: 'Tampilkan model di atas' }) as HTMLSelectElement).value,
  ).toBe('')
  expect(screen.queryByText('Mungkin kamu tertarik.')).toBeNull()
  const gpt = screen.getByRole('region', { name: 'GPT. Pilih tenaga berpikirmu.' })
  const china = screen.getByRole('region', { name: 'Perspektif baru. Banyak kemungkinan.' })
  const others = screen.getByRole('region', { name: 'Gemini dan pilihan lainnya.' })
  expect(highlight.compareDocumentPosition(gpt) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(gpt.compareDocumentPosition(china) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(china.compareDocumentPosition(others) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(
    screen.getByRole('button', { name: 'Pembelian segera tersedia' }).hasAttribute('disabled'),
  ).toBe(true)
})

test('filter pins one model above recommendations without duplicate or missing cards', async () => {
  mockCatalog()
  renderPricing()
  const select = await screen.findByRole('combobox', { name: 'Tampilkan model di atas' })
  fireEvent.change(select, { target: { value: 'gpt-5.6-sol' } })
  const pinned = screen.getByRole('region', { name: 'Paket GPT 5.6 Sol' })
  expect(within(pinned).getAllByRole('article')).toHaveLength(2)
  expect(screen.getAllByRole('article')).toHaveLength(16)
  expect(
    pinned.compareDocumentPosition(
      screen.getByRole('heading', { name: 'Mungkin kamu tertarik.' }),
    ) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy()
  fireEvent.change(select, { target: { value: '' } })
  expect(screen.queryByText('Mungkin kamu tertarik.')).toBeNull()
  expect(screen.getAllByRole('article')).toHaveLength(16)
})

test('calculator separates primary tokens from shared bonus and omits unspecified monthly Sol', async () => {
  mockCatalog()
  renderPricing()
  fireEvent.click(await screen.findByRole('button', { name: 'GPT 5.6 Sol: Simulasikan mingguan' }))
  const calc = screen.getByRole('region', { name: 'Rencanakan. Lalu berkarya.' })
  const input = within(calc).getByRole('spinbutton')
  fireEvent.change(input, { target: { value: '50' } })
  expect(within(calc).getByText(/54\.900/)).toBeTruthy()
  expect(within(calc).getByText(/Total bonus: 50 juta token/)).toBeTruthy()
  expect(
    within(within(calc).getByRole('combobox', { name: 'Periode paket' })).queryByRole('option', {
      name: 'Bulanan',
    }),
  ).toBeNull()
  fireEvent.change(input, { target: { value: '51' } })
  expect(within(calc).getByText(/109\.800/)).toBeTruthy()
  expect(within(calc).getByText(/Total bonus: 100 juta token/)).toBeTruthy()
  fireEvent.change(input, { target: { value: '-1' } })
  expect(within(calc).getByText(/Masukkan jumlah lebih dari 0/)).toBeTruthy()
})

test('monthly promo and whole-package calculations stay consistent', async () => {
  mockCatalog()
  renderPricing('/pricing?model=glm-5.3-flash')
  const pinned = await screen.findByRole('region', { name: 'Paket GLM 5.3 Flash' })
  expect(within(pinned).getByText(/22\.500/)).toBeTruthy()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Tampilkan promo bulanan' }))
  expect(within(pinned).getByText(/27\.000/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'DeepSeek V4.1 Flash: Simulasikan harian' }))
  const calc = screen.getByRole('region', { name: 'Rencanakan. Lalu berkarya.' })
  fireEvent.change(within(calc).getByRole('spinbutton'), { target: { value: '101' } })
  expect(within(calc).getByText(/19\.800/)).toBeTruthy()
  fireEvent.change(screen.getByRole('textbox', { name: 'Cari model' }), {
    target: { value: 'nonexistent' },
  })
  expect(screen.getByText('Tidak ada model yang cocok.')).toBeTruthy()
})

test('hidden SG deep link falls back safely to visible models', async () => {
  mockCatalog()
  renderPricing('/pricing?model=deepseek-v4.1-flash-sg')
  await screen.findByRole('region', { name: 'DeepSeek. Siap untuk setiap hari.' })
  expect(screen.getAllByRole('article')).toHaveLength(16)
  expect(screen.queryByText('Mungkin kamu tertarik.')).toBeNull()
  expect(
    (screen.getByRole('combobox', { name: 'Model kalkulator' }) as HTMLSelectElement).value,
  ).toBe('deepseek-v4.1-flash')
})

test('theme selection persists across mounts and follows device preference', () => {
  vi.stubGlobal('matchMedia', () => ({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
  const first = render(<ThemeToggle />)
  expect(document.documentElement.dataset.theme).toBe('dark')
  fireEvent.change(screen.getByRole('combobox', { name: 'Tema' }), { target: { value: 'light' } })
  expect(document.documentElement.dataset.theme).toBe('light')
  expect(localStorage.getItem('atheena.theme')).toBe('light')
  first.unmount()
  render(<ThemeToggle />)
  expect(document.documentElement.dataset.theme).toBe('light')
})
