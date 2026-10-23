import type { Totals, UserSummary } from './api'

export interface UserDetail extends UserSummary {
  daily_cap_idr: number | null
  active_keys: number
  created_at: string
}
export interface AdminModel {
  id: string
  public_name: string
  upstream_id: string
  api_format: 'openai' | 'anthropic' | 'both'
  provider: string
  category: 'official' | 'experimental'
  min_tier: 'basic' | 'advanced'
  is_active: boolean
  context_window: number | null
  price_input_per_m: string
  price_output_per_m: string
  price_cache_write_per_m: string
  price_cache_read_per_m: string
}
export interface SyncResult {
  upstream_total: number
  in_catalog: number
  candidates: { upstream_id: string; owned_by: string | null; suggested_public_name: string }[]
}
export interface Breakdown {
  key: string | null
  label: string
  totals: Totals
}
export interface GlobalUsage {
  totals: Totals
  by_user: Breakdown[]
  by_model: Breakdown[]
  by_project: Breakdown[]
  by_provider: Breakdown[]
}
export interface Project {
  id: string
  slug: string
  name: string
  official_only: boolean
}
export interface GatewaySettings {
  min_balance_idr: number
  default_user_daily_cap_idr: number | null
  rate_limit_per_key_per_minute: number
  rate_limit_per_user_per_minute: number
  max_concurrent_streams_per_user: number
  max_body_bytes: number
  max_active_keys_per_user: number
  default_low_balance_threshold_idr: number
}
