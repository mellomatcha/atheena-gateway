// Dashboard API client. Mutations always carry the CSRF header the backend requires.

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

type Query = Record<string, string | number | undefined>

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Query
}

const MUTATIONS = new Set(['POST', 'PATCH', 'DELETE'])

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const search = params.size > 0 ? `?${params}` : ''
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (MUTATIONS.has(method)) headers['X-Atheena-CSRF'] = '1'

  let response: Response
  try {
    response = await fetch(`/app/api${path}${search}`, {
      method,
      headers,
      credentials: 'same-origin',
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch {
    throw new ApiError(0, 'network', 'Tidak bisa menghubungi server. Periksa koneksi lalu coba lagi.')
  }
  if (response.ok) return (await response.json()) as T

  let code = 'http_error'
  let message = `Permintaan gagal (HTTP ${response.status}).`
  try {
    const data = await response.json()
    if (data?.error?.message) {
      code = data.error.code ?? code
      message = data.error.message
    } else if (response.status === 422) {
      code = 'validation'
      message = 'Isian belum valid. Periksa kembali lalu kirim ulang.'
    }
  } catch {
    // Non-JSON error body: keep the generic message.
  }
  throw new ApiError(response.status, code, message)
}

// ----- Shared API shapes -----

export interface Me {
  id: string
  email: string
  display_name: string
  role: 'member' | 'admin'
  tier: 'basic' | 'advanced'
  status: string
  balance_idr: number
  low_balance_threshold_idr: number
  daily_cap_idr: number | null
  leaderboard_opt_out: boolean
}

export type LedgerType = 'topup' | 'usage' | 'adjustment' | 'refund'

export interface LedgerEntry {
  id: string
  created_at: string
  type: LedgerType
  amount_idr: number
  balance_after_idr: number
  note: string | null
  request_id: string | null
}

export interface LedgerPage {
  items: LedgerEntry[]
  page: number
  page_size: number
  total: number
}

export interface UserSummary {
  id: string
  email: string
  display_name: string
  role: string
  tier: string
  status: string
  balance_idr: number
}
