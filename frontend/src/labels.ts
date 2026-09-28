import type { RequestRow } from './api'

// Short Indonesian labels for the gateway's error codes (requests.error_type).
const ERROR_LABELS: Record<string, string> = {
  invalid_api_key: 'Key tidak valid',
  insufficient_balance: 'Saldo habis',
  model_not_allowed: 'Model tidak diizinkan',
  daily_cap_exceeded: 'Batas harian',
  rate_limited: 'Terlalu sering',
  too_many_streams: 'Batas stream',
  body_too_large: 'Terlalu besar',
  project_official_only: 'Proyek resmi saja',
  invalid_request: 'Request tidak valid',
  upstream_rejected: 'Ditolak provider',
  upstream_rate_limited: 'Provider membatasi',
  upstream_error: 'Gagal di provider',
  upstream_unreachable: 'Provider tak terjangkau',
  upstream_timeout: 'Provider timeout',
  client_disconnected: 'Dibatalkan klien',
}

export function statusLabel(row: Pick<RequestRow, 'status_code' | 'error_type'>): string {
  if (row.status_code < 400) return 'Sukses'
  return ERROR_LABELS[row.error_type ?? ''] ?? `Gagal (${row.status_code})`
}
