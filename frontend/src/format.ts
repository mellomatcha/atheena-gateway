// Rupiah and date formatting for id-ID, always in Western Indonesia Time.

const rupiah = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 })
const dateTime = new Intl.DateTimeFormat('id-ID', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Asia/Jakarta',
})

/** 1234567 -> "1.234.567" */
export function formatNumber(value: number): string {
  return rupiah.format(value)
}

/** 1234567 -> "Rp 1.234.567", -500 -> "−Rp 500" */
export function formatIDR(value: number): string {
  const sign = value < 0 ? '−' : ''
  return `${sign}Rp ${rupiah.format(Math.abs(value))}`
}

/** Signed amount for ledgers: "+Rp 50.000" / "−Rp 1.250" */
export function formatSignedIDR(value: number): string {
  return value > 0 ? `+${formatIDR(value)}` : formatIDR(value)
}

export function formatDateTime(iso: string): string {
  return `${dateTime.format(new Date(iso))} WIB`
}

/** Keep only digits from a typed amount; returns 0 for empty input. */
export function parseDigits(text: string): number {
  const digits = text.replace(/\D/g, '').slice(0, 12)
  return digits ? Number(digits) : 0
}

const compact = new Intl.NumberFormat('id-ID', { notation: 'compact', maximumFractionDigits: 1 })
const shortDay = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', timeZone: 'UTC' })
const longDay = new Intl.DateTimeFormat('id-ID', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})

/** 1250000 -> "1,3 jt" for chart axes. */
export function formatCompact(value: number): string {
  return compact.format(value)
}

/** "2026-08-11" (a WIB calendar date) -> "11 Agu" */
export function formatShortDay(isoDay: string): string {
  return shortDay.format(new Date(`${isoDay}T00:00:00Z`))
}

/** "2026-08-11" -> "Selasa, 11 Agustus 2026" */
export function formatLongDay(isoDay: string): string {
  return longDay.format(new Date(`${isoDay}T00:00:00Z`))
}

/** Today's date in WIB as YYYY-MM-DD. */
export function todayWib(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Jakarta' }).format(new Date())
}

export function shiftDay(isoDay: string, days: number): string {
  const date = new Date(`${isoDay}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

export function formatMs(ms: number | null): string {
  if (ms === null) return '–'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1).replace('.', ',')} dtk`
}
