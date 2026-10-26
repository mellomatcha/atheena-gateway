import { useState, type FormEvent } from 'react'
import { api, ApiError, type Me } from '../api'
import { ThemeToggle } from '../components/ThemeToggle'
import { useMe } from '../session-context'

export function OnboardingPage() {
  const { me, refresh } = useMe()
  const [username, setUsername] = useState(
    /^ath_[0-9a-f]{20}$/.test(me.username) ? '' : me.username,
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const valid = /^[a-z][a-z0-9_]{2,23}$/.test(username)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!valid || saving) return
    setSaving(true)
    setError('')
    try {
      await api<Me>('/me', {
        method: 'PATCH',
        body: { username },
      })
      await refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Profil belum tersimpan. Coba lagi.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="onboarding">
      <header className="section__head">
        <a className="wordmark" href="https://atheena.online">
          ATHEENA ✳
        </a>
        <ThemeToggle />
      </header>
      <section className="panel onboarding__card">
        <span className="eyebrow">SELAMAT DATANG DI ATHEENA</span>
        <h1>Pilih username-mu.</h1>
        <p className="muted">
          Login Google berhasil untuk {me.email}. Nama lengkap diambil otomatis dari akun Google dan
          tetap privat. Pilih username untuk identitasmu di ATHEENA dan leaderboard.
        </p>
        <form className="profile-form" onSubmit={(event) => void submit(event)}>
          <label className="field">
            <span className="field__label" id="setup-username-label">
              Username publik
            </span>
            <input
              className="input"
              autoComplete="username"
              aria-labelledby="setup-username-label"
              required
              minLength={3}
              maxLength={24}
              pattern="[a-z][a-z0-9_]{2,23}"
              value={username}
              onChange={(event) => setUsername(event.target.value.toLowerCase())}
            />
            <small className="muted">
              3–24 karakter, diawali huruf. Gunakan huruf, angka, atau underscore. Ini identitasmu
              di leaderboard.
            </small>
          </label>
          {error && (
            <p role="alert" className="notice notice--error">
              {error}
            </p>
          )}
          <button type="submit" className="button button--primary" disabled={!valid || saving}>
            {saving ? 'Menyimpan…' : 'Buka workspace ↗'}
          </button>
        </form>
      </section>
    </main>
  )
}
