import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { api, type Me } from '../src/api'
import { SessionContext } from '../src/session-context'
import { Shell } from '../src/components/Shell'
import { ModelsPage } from '../src/pages/admin/Models'
import { KeysPage } from '../src/pages/Keys'
import { TopUpPage } from '../src/pages/TopUp'
import App from '../src/App'
import * as sites from '../src/sites'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
const json = (body: unknown, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
const me: Me = {
  id: 'user-1',
  email: 'user@example.test',
  display_name: 'Dafin',
  full_name: 'Dafin',
  username: 'dafin',
  role: 'member',
  tier: 'basic',
  status: 'active',
  balance_idr: 5000,
  low_balance_threshold_idr: 1000,
  daily_cap_idr: null,
  leaderboard_opt_out: false,
}

test('member navigation cannot expose administration pages', () => {
  render(
    <MemoryRouter>
      <SessionContext value={{ state: { status: 'ready', me }, refresh: async () => {} }}>
        <Shell />
      </SessionContext>
    </MemoryRouter>,
  )
  expect(screen.getByRole('link', { name: 'API key' })).toBeTruthy()
  expect(screen.queryByRole('link', { name: 'Pengguna' })).toBeNull()
  expect(screen.queryByRole('link', { name: 'Katalog & harga' })).toBeNull()
})

test('production dashboard sends admins to the separate console', () => {
  vi.spyOn(sites, 'getSurface').mockReturnValue('dashboard')
  render(
    <MemoryRouter>
      <SessionContext
        value={{
          state: { status: 'ready', me: { ...me, role: 'admin' } },
          refresh: async () => {},
        }}
      >
        <Shell />
      </SessionContext>
    </MemoryRouter>,
  )
  expect(screen.getByRole('link', { name: 'API key' })).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Console admin ↗' }).getAttribute('href')).toContain(
    'console.atheena.online',
  )
  expect(screen.queryByRole('link', { name: 'Pengguna' })).toBeNull()
})

test('console navigation contains administration and a return to dashboard', () => {
  vi.spyOn(sites, 'getSurface').mockReturnValue('console')
  render(
    <MemoryRouter>
      <SessionContext
        value={{
          state: { status: 'ready', me: { ...me, role: 'admin' } },
          refresh: async () => {},
        }}
      >
        <Shell />
      </SessionContext>
    </MemoryRouter>,
  )
  expect(screen.getByRole('link', { name: 'Pengguna' })).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Dashboard pengguna ↗' })).toBeTruthy()
  expect(screen.queryByRole('link', { name: 'API key' })).toBeNull()
})

test('expired authentication stops before rendering workspace', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => json({ error: { code: 'unauthenticated', message: 'Sign in' } }, 401)),
  )
  render(<App />)
  await screen.findByRole('heading', { name: 'Sesi berakhir' })
  expect(screen.queryByRole('navigation', { name: 'Menu utama' })).toBeNull()
})

test('mutations include CSRF protection and same-origin session', async () => {
  const fetch = vi.fn(() => json({ ok: true }))
  vi.stubGlobal('fetch', fetch)
  await api('/admin/settings', { method: 'PATCH', body: { min_balance_idr: 1000 } })
  expect(fetch).toHaveBeenCalledWith(
    '/app/api/admin/settings',
    expect.objectContaining({
      method: 'PATCH',
      credentials: 'same-origin',
      headers: expect.objectContaining({ 'X-Atheena-CSRF': '1' }),
    }),
  )
})

test('catalog sync requires explicit save and new models stay inactive', async () => {
  const fetch = vi.fn((url: string, options?: RequestInit) => {
    if (url.endsWith('/sync'))
      return json({
        upstream_total: 1,
        in_catalog: 0,
        candidates: [
          {
            upstream_id: 'cbai/test-model',
            suggested_public_name: 'test-model',
            owned_by: 'codebuddy',
          },
        ],
      })
    if (options?.method === 'POST') return json({ id: 'new-model' }, 201)
    return json([])
  })
  vi.stubGlobal('fetch', fetch)
  render(<ModelsPage />)
  fireEvent.click(screen.getByRole('button', { name: 'Periksa model 9Router' }))
  fireEvent.click(await screen.findByRole('button', { name: 'cbai/test-model +' }))
  expect(
    fetch.mock.calls.filter(
      ([url, options]) => url.endsWith('/models') && options?.method === 'POST',
    ),
  ).toHaveLength(0)
  fireEvent.click(screen.getByRole('button', { name: 'Simpan model' }))
  await screen.findByRole('status')
  const call = fetch.mock.calls.find(
    ([url, options]) => url.endsWith('/models') && options?.method === 'POST',
  )
  expect(call).toBeTruthy()
  expect(JSON.parse(call![1]!.body as string)).toMatchObject({
    public_name: 'test-model',
    upstream_id: 'cbai/test-model',
    is_active: false,
    price_input_per_m: '0',
  })
})

test('API key is shown once, can be dismissed, and is never put into local storage', async () => {
  const key = 'sk-ath-THIS_IS_A_TEST_KEY_NOT_A_REAL_CREDENTIAL'
  const fetch = vi.fn((url: string, options?: RequestInit) => {
    if (url.endsWith('/keys') && options?.method === 'POST')
      return json(
        { id: 'key-1', name: 'laptop', key, prefix: key.slice(0, 12), status: 'active' },
        201,
      )
    return json([])
  })
  const storage = vi.spyOn(Storage.prototype, 'setItem')
  vi.stubGlobal('fetch', fetch)
  render(
    <MemoryRouter>
      <KeysPage />
    </MemoryRouter>,
  )
  fireEvent.change(screen.getByLabelText('Nama key'), { target: { value: 'laptop' } })
  fireEvent.submit(screen.getByLabelText('Nama key').closest('form')!)
  await screen.findByText(key)
  fireEvent.click(screen.getByRole('button', { name: 'Sudah saya simpan' }))
  await waitFor(() => expect(screen.queryByText(key)).toBeNull())
  expect(storage).not.toHaveBeenCalled()
})

test('unconfigured payments do not display the sample QRIS or payment action', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      url.endsWith('/topup-info')
        ? json({
            payments_enabled: false,
            qris_image_path: '/assets/qris.png',
            whatsapp_number: '0',
          })
        : json({ items: [], page: 1, page_size: 50, total: 0 }),
    ),
  )
  render(
    <SessionContext value={{ state: { status: 'ready', me }, refresh: async () => {} }}>
      <TopUpPage />
    </SessionContext>,
  )
  await screen.findByText('Pembayaran belum diaktifkan. Hubungi admin untuk informasi saldo.')
  expect(screen.queryByRole('img', { name: /QRIS/ })).toBeNull()
  expect(screen.queryByRole('link', { name: 'Konfirmasi via WhatsApp' })).toBeNull()
})
