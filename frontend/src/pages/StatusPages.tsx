import { useState } from 'react'
import { useMe } from '../session-context'
import { ThemeToggle } from '../components/ThemeToggle'

export function PendingPage() {
  const { me, refresh } = useMe()
  const [busy, setBusy] = useState(false)
  async function check() {
    setBusy(true)
    try {
      await refresh()
    } finally {
      setBusy(false)
    }
  }
  return (
    <main className="status-page">
      <span className="wordmark">ATHEENA ✳</span>
      <ThemeToggle />
      <h1>Menunggu aktivasi admin.</h1>
      <p className="muted">
        Profil @{me.username} sudah tersimpan untuk {me.email}. Admin akan meninjau akunmu sebelum
        akses API dibuka.
      </p>
      <p>
        <button className="button button--primary" onClick={() => void check()} disabled={busy}>
          {busy ? 'Memeriksa…' : 'Periksa status aktivasi'}
        </button>
      </p>
      <a href="https://atheena.online/pricing">Lihat pilihan paket ↗</a>
    </main>
  )
}

export function InactivePage() {
  return (
    <main className="status-page">
      <span className="wordmark">Atheena</span>
      <h1>Akun belum aktif</h1>
      <p className="muted">
        Email Anda sudah lolos login, tetapi belum terdaftar sebagai pengguna aktif di Atheena.
        Hubungi admin untuk mengaktifkan akun.
      </p>
    </main>
  )
}

export function SignedOutPage() {
  return (
    <main className="status-page">
      <span className="wordmark">Atheena</span>
      <h1>Sesi berakhir</h1>
      <p className="muted">Muat ulang halaman untuk masuk lagi lewat Google.</p>
      <p>
        <button className="button button--primary" onClick={() => window.location.reload()}>
          Muat ulang
        </button>
      </p>
    </main>
  )
}

export function ErrorPage({ message }: { message: string }) {
  return (
    <main className="status-page">
      <span className="wordmark">Atheena</span>
      <h1>Portal tidak bisa dimuat</h1>
      <p className="notice notice--error">{message}</p>
      <p>
        <button className="button" onClick={() => window.location.reload()}>
          Coba lagi
        </button>
      </p>
    </main>
  )
}
