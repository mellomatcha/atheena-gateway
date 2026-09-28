import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { api, ApiError, type ApiKey, type CatalogModel, type CreatedKey } from '../api'
import { CopyButton } from '../components/CopyButton'
import { formatDateTime, formatIDR, formatNumber, parseDigits } from '../format'
import { useAsync } from '../useAsync'

export function KeysPage() {
  const navigate = useNavigate()
  const keys = useAsync('keys', () => api<ApiKey[]>('/keys'))
  const models = useAsync('models', () => api<CatalogModel[]>('/models'))
  const [name, setName] = useState('')
  const [cap, setCap] = useState(0)
  const [allowlist, setAllowlist] = useState<string[]>([])
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string>()
  const [created, setCreated] = useState<CreatedKey>()
  const [revoking, setRevoking] = useState<string>()

  const active = keys.data?.filter((k) => k.status === 'active') ?? []

  async function create(event: FormEvent) {
    event.preventDefault()
    setCreating(true)
    setError(undefined)
    try {
      const key = await api<CreatedKey>('/keys', {
        method: 'POST',
        body: {
          name: name.trim(),
          daily_cap_idr: cap > 0 ? cap : null,
          model_allowlist: allowlist.length > 0 ? allowlist : null,
        },
      })
      setCreated(key)
      setName('')
      setCap(0)
      setAllowlist([])
      keys.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Gagal membuat key.')
    } finally {
      setCreating(false)
    }
  }

  async function revoke(id: string) {
    setError(undefined)
    try {
      await api(`/keys/${id}`, { method: 'DELETE' })
      setRevoking(undefined)
      if (created?.id === id) setCreated(undefined)
      keys.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Gagal mencabut key.')
    }
  }

  return (
    <div className="page">
      <header className="page__head">
        <h1>API key</h1>
        <p className="muted">
          Satu key cukup untuk semua model dan semua tool. Buat key terpisah per perangkat supaya
          mudah dicabut kalau perangkat hilang.
        </p>
      </header>

      {created && (
        <section className="panel new-key" aria-labelledby="key-baru" role="status">
          <h2 id="key-baru">Key "{created.name}" dibuat</h2>
          <p>Salin sekarang. Key ini hanya ditampilkan sekali dan tidak bisa dilihat lagi.</p>
          <div className="new-key__value">
            <code className="num">{created.key}</code>
            <CopyButton text={created.key} label="Salin key" />
          </div>
          <p className="chips">
            <button
              type="button"
              className="button button--primary"
              onClick={() => navigate('/app/mulai', { state: { newKey: created.key } })}
            >
              Pasang di OpenCode atau Claude Code
            </button>
            <button type="button" className="button" onClick={() => setCreated(undefined)}>
              Sudah saya simpan
            </button>
          </p>
        </section>
      )}

      <section className="section" aria-labelledby="buat-key">
        <h2 id="buat-key">Buat key baru</h2>
        <form className="key-form" onSubmit={(e) => void create(e)}>
          <label className="field">
            <span className="field__label">Nama key</span>
            <input
              className="input"
              required
              maxLength={60}
              placeholder="misalnya laptop-kantor"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <details className="key-form__more">
            <summary>Batasan opsional</summary>
            <label className="field">
              <span className="field__label">Batas biaya harian key ini (Rupiah)</span>
              <input
                className="input input--amount"
                inputMode="numeric"
                placeholder="tanpa batas"
                value={cap ? formatNumber(cap) : ''}
                onChange={(e) => setCap(parseDigits(e.target.value))}
              />
            </label>
            <fieldset className="field">
              <legend className="field__label">
                Hanya izinkan model tertentu (kosongkan untuk semua model)
              </legend>
              <div className="checks">
                {models.data?.map((m) => (
                  <label key={m.name} className="check">
                    <input
                      type="checkbox"
                      checked={allowlist.includes(m.name)}
                      onChange={(e) =>
                        setAllowlist((current) =>
                          e.target.checked ? [...current, m.name] : current.filter((x) => x !== m.name),
                        )
                      }
                    />
                    {m.name}
                  </label>
                ))}
              </div>
            </fieldset>
          </details>
          {error && <p className="notice notice--error">{error}</p>}
          <p>
            <button type="submit" className="button button--primary" disabled={creating || !name.trim()}>
              {creating ? 'Membuat…' : 'Buat key'}
            </button>
          </p>
        </form>
      </section>

      <section className="section" aria-labelledby="daftar-key">
        <div className="section__head">
          <h2 id="daftar-key">Key saya</h2>
          <span className="muted num">{active.length} aktif</span>
        </div>
        {keys.error && <p className="notice notice--error">{keys.error.message}</p>}
        {keys.data && keys.data.length === 0 && (
          <div className="table-wrap empty">Belum ada key. Buat satu di atas untuk mulai memakai model.</div>
        )}
        {keys.data && keys.data.length > 0 && (
          <div className="table-wrap">
            <table className="table table--keys">
              <thead>
                <tr>
                  <th scope="col">Nama</th>
                  <th scope="col">Dibuat</th>
                  <th scope="col">Terakhir dipakai</th>
                  <th scope="col" className="right">
                    Pemakaian
                  </th>
                  <th scope="col">Status</th>
                  <th scope="col">
                    <span className="visually-hidden">Aksi</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {keys.data.map((key) => (
                  <tr key={key.id}>
                    <td>
                      {key.name}
                      <span className="cell-sub num muted">{key.prefix}…</span>
                    </td>
                    <td className="num muted">{formatDateTime(key.created_at)}</td>
                    <td className="num muted">
                      {key.last_used_at ? formatDateTime(key.last_used_at) : 'Belum pernah'}
                    </td>
                    <td className="num right">
                      {formatIDR(key.usage.cost_idr)}
                      <span className="cell-sub muted">{formatNumber(key.usage.requests)} request</span>
                    </td>
                    <td>
                      <span className="status" data-ok={key.status === 'active'}>
                        {key.status === 'active' ? 'Aktif' : 'Dicabut'}
                      </span>
                    </td>
                    <td className="right">
                      {key.status === 'active' &&
                        (revoking === key.id ? (
                          <span className="chips chips--end">
                            <button type="button" className="button button--danger" onClick={() => void revoke(key.id)}>
                              Ya, cabut
                            </button>
                            <button type="button" className="button" onClick={() => setRevoking(undefined)}>
                              Batal
                            </button>
                          </span>
                        ) : (
                          <button type="button" className="button" onClick={() => setRevoking(key.id)}>
                            Cabut
                          </button>
                        ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
