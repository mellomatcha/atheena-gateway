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
      <p className="muted">Muat ulang halaman untuk masuk lagi lewat login Google kantor.</p>
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
