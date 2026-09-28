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

export interface Totals {
  requests: number
  tokens: number
  input_tokens: number
  output_tokens: number
  cache_write_tokens: number
  cache_read_tokens: number
  cost_idr: number
}

export interface Summary {
  balance_idr: number
  today: Totals
  last_7_days: Totals
  last_30_days: Totals
  top_model_30_days: string | null
}

export interface DayPoint {
  day: string
  value: number
  totals: Totals
}

export interface Timeseries {
  unit: 'token' | 'idr'
  start: string
  end: string
  points: DayPoint[]
  range_totals: Totals
}

export interface RequestRow {
  request_id: string
  started_at: string
  model: string | null
  project: string | null
  endpoint: string
  stream: boolean
  status_code: number
  error_type: string | null
  input_tokens: number
  output_tokens: number
  cache_write_tokens: number
  cache_read_tokens: number
  usage_estimated: boolean
  cost_idr: number
  latency_ms: number | null
  ttft_ms: number | null
  key_id: string | null
  key_name: string | null
  key_prefix: string | null
  user_id: string | null
  user_name: string | null
}

export interface RequestPage {
  items: RequestRow[]
  page: number
  page_size: number
  total: number
}

export interface ApiKey {
  id: string
  name: string
  prefix: string
  status: 'active' | 'revoked'
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
  daily_cap_idr: number | null
  model_allowlist: string[] | null
  usage: Omit<Totals, 'tokens'>
}

export interface CreatedKey extends ApiKey {
  key: string
}

export interface CatalogModel {
  name: string
  api_format: 'openai' | 'anthropic' | 'both'
  category: 'official' | 'experimental'
  min_tier: string
  context_window: number | null
  price_input_per_m: string
  price_output_per_m: string
  price_cache_write_per_m: string
  price_cache_read_per_m: string
}

export interface Facets {
  models: string[]
  projects: string[]
}
