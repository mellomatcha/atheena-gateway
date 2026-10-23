import { errorMessage } from '../../errors'
import { useState, type FormEvent } from 'react'
import { api } from '../../api'
import type { GatewaySettings, Project } from '../../admin-types'
import { Field, Feedback, PageHead } from '../../components/AdminUI'
import { useAsync } from '../../useAsync'

const fields: [keyof GatewaySettings, string, number, number][] = [
  ['min_balance_idr', 'Saldo minimum (Rp)', 0, 100000000],
  ['default_low_balance_threshold_idr', 'Peringatan saldo default (Rp)', 0, 100000000],
  ['default_user_daily_cap_idr', 'Batas harian default (Rp), kosong = tanpa batas', 1, 1000000000],
  ['rate_limit_per_key_per_minute', 'Request / menit / key', 1, 100000],
  ['rate_limit_per_user_per_minute', 'Request / menit / pengguna', 1, 100000],
  ['max_concurrent_streams_per_user', 'Stream bersamaan / pengguna', 1, 1000],
  ['max_body_bytes', 'Ukuran request maksimum (byte)', 1024, 209715200],
  ['max_active_keys_per_user', 'API key aktif / pengguna', 1, 100],
]
function SettingsForm({ values, reload }: { values: GatewaySettings; reload: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    const body = Object.fromEntries(
      fields.map(([name]) => [name, data.get(name) === '' ? null : Number(data.get(name))]),
    )
    if (
      !window.confirm('Terapkan batas baru untuk gateway? Perubahan berlaku untuk semua pengguna.')
    )
      return
    setBusy(true)
    setError('')
    setSaved('')
    try {
      await api('/admin/settings', { method: 'PATCH', body })
      setSaved('Pengaturan disimpan dan diaudit.')
      reload()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="panel editor" onSubmit={save}>
      <h2>Batas & pemakaian</h2>
      <div className="form-grid">
        {fields.map(([name, label, min, max]) => (
          <Field key={name} label={label}>
            <input
              className="input"
              type="number"
              name={name}
              min={min}
              max={max}
              step="1"
              required={name !== 'default_user_daily_cap_idr'}
              defaultValue={values[name] ?? ''}
            />
          </Field>
        ))}
      </div>
      <Feedback error={error} success={saved} />
      <button className="button button--primary" disabled={busy}>
        {busy ? 'Menyimpan…' : 'Simpan pengaturan'}
      </button>
    </form>
  )
}
function ProjectForm({ project, reload }: { project?: Project; reload: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const data = new FormData(form)
    const body = {
      name: data.get('name'),
      official_only: data.get('official_only') === 'on',
      ...(!project ? { slug: data.get('slug') } : {}),
    }
    setBusy(true)
    setError('')
    try {
      await api(`/admin/projects${project ? `/${project.id}` : ''}`, {
        method: project ? 'PATCH' : 'POST',
        body,
      })
      if (!project) form.reset()
      reload()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="panel editor" onSubmit={save}>
      <h3>{project ? project.slug : 'Proyek baru'}</h3>
      <div className="form-grid">
        {!project && (
          <Field label="Slug untuk X-Project">
            <input
              className="input"
              name="slug"
              required
              maxLength={64}
              pattern="[a-z0-9][a-z0-9_\-]*"
              placeholder="nama-proyek"
            />
          </Field>
        )}
        <Field label="Nama proyek">
          <input
            className="input"
            name="name"
            required
            maxLength={80}
            defaultValue={project?.name}
          />
        </Field>
      </div>
      <label className="check">
        <input
          type="checkbox"
          name="official_only"
          defaultChecked={project?.official_only ?? false}
        />{' '}
        Hanya model resmi
      </label>
      <Feedback error={error} />
      <button className="button" disabled={busy}>
        {busy ? 'Menyimpan…' : 'Simpan proyek'}
      </button>
    </form>
  )
}
export function SettingsPage() {
  const settings = useAsync('settings', () => api<GatewaySettings>('/admin/settings'))
  const projects = useAsync('projects', () => api<Project[]>('/admin/projects'))
  return (
    <div className="page">
      <PageHead
        title="Pengaturan gateway"
        description="Tetapkan batas yang masuk akal dan pisahkan pemakaian per proyek."
      />
      <Feedback error={settings.error?.message ?? projects.error?.message} />
      {settings.data ? (
        <SettingsForm values={settings.data} reload={settings.reload} />
      ) : (
        <p>Memuat pengaturan…</p>
      )}
      <section className="section">
        <h2>Proyek</h2>
        <p className="muted">
          Kirim header X-Project dengan slug proyek untuk mencatat pemakaian dan menerapkan batas
          kategori model.
        </p>
        {projects.data?.map((p) => (
          <ProjectForm key={p.id} project={p} reload={projects.reload} />
        ))}
        <ProjectForm reload={projects.reload} />
      </section>
    </div>
  )
}
