import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
    context_window: 1000000,
    inference_verified: true,
  },
  {
    id: 'glm-5.3-flash',
    name: 'GLM 5.3 Flash',
    provider: 'Zhipu',
    multiplier: '0.45',
    context_window: 1000000,
    inference_verified: true,
  },
]
const plans = [
  { id: 'daily', name: 'Harian', days: 1, tokens: 100000000, price_idr: 9900, regular_idr: 9900 },
  {
    id: 'weekly',
    name: 'Mingguan',
    days: 7,
    tokens: 250000000,
    price_idr: 34900,
    regular_idr: 34900,
  },
  {
    id: 'monthly',
    name: 'Bulanan',
    days: 30,
    tokens: 500000000,
    price_idr: 49900,
    regular_idr: 59900,
  },
]
function mockCatalog() {
  const fetcher = vi.fn((path: string) => {
    const url = new URL(path, 'https://test.example')
    const plan = plans.find((p) => p.id === url.searchParams.get('plan'))!
    const factor = url.searchParams.get('model') === 'glm-5.3-flash' ? 0.45 : 1
    const price =
      plan &&
      Math.ceil(
        ((url.searchParams.get('promo') === 'false' ? plan.regular_idr : plan.price_idr) * factor) /
          100,
      ) * 100
    const body = path.endsWith('/catalog')
      ? { models, plans, version: '2.173.0', captured_at: '2026-10-23T00:00:00Z' }
      : {
          model: url.searchParams.get('model'),
          plan: plan.id,
          price_idr: price,
          regular_idr: Math.ceil((plan.regular_idr * factor) / 100) * 100,
          included_tokens: plan.tokens,
          effective_idr_per_million: String(price / (plan.tokens / 1000000)),
        }
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

test('public pricing works without a session, rounds full packages and rejects invalid quantity', async () => {
  const fetcher = mockCatalog()
  render(
    <MemoryRouter>
      <PricingPage />
    </MemoryRouter>,
  )
  await screen.findByRole('heading', { name: 'Bulanan' })
  await waitFor(() => expect(screen.getAllByText(/49\.900/).length).toBeGreaterThan(0))
  fireEvent.click(screen.getByRole('button', { name: /Simulasikan harian/ }))
  fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '101' } })
  await screen.findByText(/19\.800/)
  fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '-1' } })
  expect(screen.getByText(/Masukkan jumlah lebih dari 0/)).toBeTruthy()
  expect(fetcher.mock.calls.every(([path]) => path.startsWith('/api/public/'))).toBe(true)
  expect(
    screen.getByRole('button', { name: 'Pembelian segera tersedia' }).hasAttribute('disabled'),
  ).toBe(true)
})

test('homepage model link selects the model and promo toggle changes the retail quote', async () => {
  mockCatalog()
  render(
    <MemoryRouter initialEntries={['/pricing?model=glm-5.3-flash']}>
      <PricingPage />
    </MemoryRouter>,
  )
  await screen.findByRole('heading', { name: 'Bulanan' })
  await waitFor(() => expect(screen.getAllByText(/22\.500/).length).toBeGreaterThan(0))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Tampilkan promo bulanan' }))
  await waitFor(() => expect(screen.getAllByText(/27\.000/).length).toBeGreaterThan(0))
  fireEvent.change(screen.getByRole('textbox', { name: 'Cari model' }), {
    target: { value: 'nonexistent' },
  })
  expect(screen.getByText('Tidak ada model yang cocok.')).toBeTruthy()
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
