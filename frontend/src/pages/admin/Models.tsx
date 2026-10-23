import { errorMessage } from '../../errors'
import { useState, type FormEvent } from 'react'
import { api } from '../../api'
import type { AdminModel, SyncResult } from '../../admin-types'
import { Field, Feedback, PageHead } from '../../components/AdminUI'
import { formatIDR } from '../../format'
import { useAsync } from '../../useAsync'

const prices = [
  ['price_input_per_m', 'Input'],
  ['price_output_per_m', 'Output'],
  ['price_cache_write_per_m', 'Cache write'],
  ['price_cache_read_per_m', 'Cache read'],
] as const
type Draft = Partial<AdminModel>
function ModelEditor({ model, onSaved }: { model: Draft; onSaved: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    const body = {
      ...Object.fromEntries(data.entries()),
      is_active: data.get('is_active') === 'on',
      context_window: data.get('context_window') ? Number(data.get('context_window')) : null,
    }
    if (
      model.id &&
      !window.confirm(
        'Simpan perubahan katalog dan harga? Harga baru berlaku untuk request berikutnya.',
      )
    )
      return
    setBusy(true)
    setError('')
    try {
      await api(`/admin/models${model.id ? `/${model.id}` : ''}`, {
        method: model.id ? 'PATCH' : 'POST',
        body,
      })
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="panel editor" onSubmit={save}>
      <h2>{model.id ? `Edit ${model.public_name}` : 'Tambahkan ke katalog'}</h2>
      <div className="form-grid">
        <Field label="Nama publik">
          <input
            className="input"
            name="public_name"
            defaultValue={model.public_name}
            required
            maxLength={63}
            pattern="[a-z0-9][a-z0-9.\-]*"
            placeholder="deepseek-v4.1-flash"
          />
        </Field>
        <Field label="ID model di 9Router">
          <input
            className="input"
            name="upstream_id"
            defaultValue={model.upstream_id}
            required
            maxLength={200}
          />
        </Field>
        <Field label="Provider">
          <input
            className="input"
            name="provider"
            defaultValue={model.provider}
            required
            maxLength={60}
          />
        </Field>
        <Field label="Format API">
          <select className="input" name="api_format" defaultValue={model.api_format ?? 'both'}>
            <option value="both">OpenAI + Anthropic</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </Field>
        <Field label="Kategori">
          <select className="input" name="category" defaultValue={model.category ?? 'experimental'}>
            <option value="experimental">Eksperimental</option>
            <option value="official">Resmi</option>
          </select>
        </Field>
        <Field label="Tier minimum">
          <select className="input" name="min_tier" defaultValue={model.min_tier ?? 'basic'}>
            <option value="basic">Basic</option>
            <option value="advanced">Advanced</option>
          </select>
        </Field>
        <Field label="Context window, opsional">
          <input
            className="input"
            name="context_window"
            type="number"
            min="1"
            step="1"
            defaultValue={model.context_window ?? ''}
          />
        </Field>
        {prices.map(([name, label]) => (
          <Field key={name} label={`${label} · Rp / 1 juta token`}>
            <input
              className="input"
              name={name}
              type="number"
              min="0"
              step="0.01"
              max="999999999999.99"
              required
              defaultValue={model[name] ?? '0'}
            />
          </Field>
        ))}
      </div>
      <label className="check">
        <input type="checkbox" name="is_active" defaultChecked={model.is_active ?? false} />{' '}
        Aktifkan model untuk pengguna yang memenuhi tier
      </label>
      <Feedback error={error} />
      <button className="button button--primary" disabled={busy}>
        {busy ? 'Menyimpan…' : 'Simpan model'}
      </button>
    </form>
  )
}

export function ModelsPage() {
  const models = useAsync('admin-models', () => api<AdminModel[]>('/admin/models'))
  const [draft, setDraft] = useState<Draft | null>(null)
  const [sync, setSync] = useState<SyncResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  async function synchronize() {
    setBusy(true)
    setError('')
    try {
      setSync(await api<SyncResult>('/admin/models/sync', { method: 'POST' }))
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="page">
      <PageHead
        title="Katalog & harga"
        description="Satu nama model untuk pengguna. Routing, akses, dan harga diatur di sini."
      />
      <div className="actions">
        <button
          className="button button--primary"
          onClick={() => {
            setDraft({})
            setSaved('')
          }}
        >
          + Model
        </button>
        <button className="button" onClick={synchronize} disabled={busy}>
          {busy ? 'Memeriksa 9Router…' : 'Periksa model 9Router'}
        </button>
      </div>
      <Feedback error={error || models.error?.message} success={saved} />
      {sync && (
        <section className="section">
          <h2>{sync.candidates.length} model belum masuk katalog</h2>
          <p className="muted">
            Pilih model untuk meninjau harga dan akses sebelum mengaktifkannya.
          </p>
          <div className="candidate-list">
            {sync.candidates.map((c) => (
              <button
                className="button"
                key={c.upstream_id}
                onClick={() =>
                  setDraft({
                    upstream_id: c.upstream_id,
                    public_name: c.suggested_public_name,
                    provider: c.owned_by ?? '',
                    is_active: false,
                  })
                }
              >
                {c.upstream_id} +
              </button>
            ))}
          </div>
        </section>
      )}
      {draft && (
        <ModelEditor
          key={JSON.stringify(draft)}
          model={draft}
          onSaved={() => {
            setDraft(null)
            setSync(null)
            setSaved('Katalog disimpan. Perubahan tersedia di audit log.')
            models.reload()
          }}
        />
      )}
      {models.loading && <p role="status">Memuat katalog…</p>}
      {models.data && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Akses</th>
                <th>Input / 1M</th>
                <th>Output / 1M</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {models.data.map((m) => (
                <tr key={m.id}>
                  <td>
                    <strong>{m.public_name}</strong>
                    <br />
                    <span className="muted">
                      {m.upstream_id} · {m.api_format}
                    </span>
                  </td>
                  <td>
                    {m.category}
                    <br />
                    {m.min_tier}
                  </td>
                  <td className="num money">{formatIDR(Number(m.price_input_per_m))}</td>
                  <td className="num money">{formatIDR(Number(m.price_output_per_m))}</td>
                  <td>{m.is_active ? 'Aktif' : 'Nonaktif'}</td>
                  <td>
                    <button className="button" onClick={() => setDraft(m)}>
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
              {!models.data.length && (
                <tr>
                  <td colSpan={6}>Katalog masih kosong. Periksa model di 9Router untuk mulai.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
