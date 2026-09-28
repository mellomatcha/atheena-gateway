import { formatIDR } from './format'

/** wa.me link with the confirmation message pre-filled (FR-5.3 step 2). */
export function whatsappLink(number: string, name: string, email: string, amount: number): string {
  const text = [
    'Halo Admin Atheena, saya ingin konfirmasi top-up saldo.',
    '',
    `Nama: ${name}`,
    `Email: ${email}`,
    `Nominal: ${formatIDR(amount)}`,
    '',
    'Bukti pembayaran saya lampirkan di chat ini.',
  ].join('\n')
  return `https://wa.me/${number.replace(/\D/g, '')}?text=${encodeURIComponent(text)}`
}
