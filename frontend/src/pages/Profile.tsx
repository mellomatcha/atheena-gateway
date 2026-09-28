import { useState, type FormEvent } from 'react'
import { api, ApiError, type Me } from '../api'
import { formatNumber, parseDigits } from '../format'
import { useMe } from '../session-context'

export function ProfilePage() {
  const { me, refresh } = useMe()
  const [name, setName] = useState(me.display_name)
  const [threshold, setThreshold] = useState(me.low_balance_threshold_idr)
  const [optOut, setOptOut] = useState(me.leaderboard_opt_out)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string }>()

  async function save(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setMessage(undefined)
    try {
      await api<Me>('/me', {
        method: 'PATCH',
        body: { display_name: name.trim(), low_balance_threshold_idr: threshold, leaderboard_opt_out: optOut },
      })
      await refresh()
      setMessage({ ok: true, text: 'Pengaturan disimpan.' })
    } catch (err) {
      setMessage({ ok: false, text: err instanceof ApiError ? err.message : 'Gagal menyimpan.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page">
      <header className="page__head">
        <h1>Pengaturan</h1>
        <p className="muted">
          {me.email}, tier {me.tier === 'advanced' ? 'advanced' : 'basic'}.
        </p>
      </header>
      <form className="profile-form" onSubmit={(e) => void save(e)}>
        <label className="field">
          <span className="field__label">Nama tampilan (dipakai di leaderboard)</span>
          <input className="input" required maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field">
          <span className="field__label">Peringatkan saya saat saldo di bawah (Rupiah)</span>
          <input
            className="input input--amount"
            inputMode="numeric"
            value={formatNumber(threshold)}
            onChange={(e) => setThreshold(parseDigits(e.target.value))}
          />
        </label>
        <label className="check">
          <input type="checkbox" checked={optOut} onChange={(e) => setOptOut(e.target.checked)} />
          Sembunyikan nama saya dari leaderboard
        </label>
        {message && (
          <p className={`notice ${message.ok ? 'notice--ok' : 'notice--error'}`} role="status">
            {message.text}
          </p>
        )}
        <p>
          <button type="submit" className="button button--primary" disabled={saving || !name.trim()}>
            {saving ? 'Menyimpan…' : 'Simpan pengaturan'}
          </button>
        </p>
      </form>
    </div>
  )
}
