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
