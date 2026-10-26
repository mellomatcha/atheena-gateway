import { errorMessage } from '../../errors'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { api, type UserSummary } from '../../api'
import type { UserDetail } from '../../admin-types'
import { Field, Feedback, PageHead } from '../../components/AdminUI'
import { formatIDR } from '../../format'
import { useMe } from '../../session-context'
import { useAsync } from '../../useAsync'

function UserEditor({ user, onSaved }: { user: UserDetail | null; onSaved: () => void }) {
  const { me } = useMe()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const body = {
      display_name: String(data.get('display_name')).trim(),
      tier: data.get('tier'),
      role: data.get('role'),
      ...(user
        ? {
            status: data.get('status'),
            daily_cap_idr: data.get('daily_cap_idr') ? Number(data.get('daily_cap_idr')) : null,
          }
        : { email: data.get('email') }),
    }
    if (
      user &&
      (body.role !== user.role || ('status' in body && body.status !== user.status)) &&
      !window.confirm(`Ubah akses ${user.email}? Perubahan berlaku pada request berikutnya.`)
    )
      return
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      await api(`/admin/users${user ? `/${user.id}` : ''}`, {
        method: user ? 'PATCH' : 'POST',
        body,
      })
      setSuccess(
        user
          ? 'Pengguna diperbarui.'
          : 'Pengguna ditambahkan. Minta pengguna masuk lewat Google dan melengkapi profil.',
      )
      if (!user) form.reset()
      onSaved()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="panel editor" onSubmit={save}>
      <h2>{user ? user.display_name : 'Tambah pengguna'}</h2>
      <div className="form-grid">
        <Field label="Nama tampilan">
          <input
            className="input"
            name="display_name"
            defaultValue={user?.display_name}
            required
            maxLength={60}
            pattern=".*\S.*"
          />
        </Field>
        {!user && (
          <Field label="Email Google">
            <input
              className="input"
              name="email"
              type="email"
              autoComplete="off"
              required
              maxLength={254}
            />
          </Field>
        )}
        <Field label="Tier">
          <select className="input" name="tier" defaultValue={user?.tier ?? 'basic'}>
            <option value="basic">Basic</option>
            <option value="advanced">Advanced</option>
          </select>
        </Field>
        <Field label="Peran">
          <select
            className="input"
            name="role"
            defaultValue={user?.role ?? 'member'}
            disabled={user?.id === me.id}
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
          {user?.id === me.id && <input type="hidden" name="role" value="admin" />}
        </Field>
        {user && (
          <>
            <Field label="Status">
              <select
                className="input"
                name="status"
                defaultValue={user.status}
                disabled={user.id === me.id}
              >
                <option value="active">Aktif</option>
                <option value="pending">Menunggu</option>
                <option value="suspended">Ditangguhkan</option>
              </select>
              {user.id === me.id && <input type="hidden" name="status" value="active" />}
            </Field>
            <Field label="Batas harian (Rp), kosong = default">
              <input
                className="input"
                name="daily_cap_idr"
                type="number"
                min="1"
                step="1"
                defaultValue={user.daily_cap_idr ?? ''}
              />
            </Field>
          </>
        )}
      </div>
      {user && (
        <p className="muted">
          {user.email} · {user.active_keys} key aktif · Saldo {formatIDR(user.balance_idr)}
        </p>
      )}
      <Feedback error={error} success={success} />
      <div className="actions">
        <button className="button button--primary" disabled={busy}>
          {busy ? 'Menyimpan…' : 'Simpan pengguna'}
        </button>
        {user && (
          <Link className="button" to="/app/admin/saldo">
            Kelola saldo
          </Link>
        )}
      </div>
    </form>
  )
}

export function UsersPage() {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState('')
  const users = useAsync(`users:${search}`, () =>
    api<UserSummary[]>('/admin/users', { query: { q: search } }),
  )
  const detail = useAsync(`user:${selected}`, () =>
    selected ? api<UserDetail>(`/admin/users/${selected}`) : Promise.resolve(null),
  )
  return (
    <div className="page">
      <PageHead
        title="Pengguna"
        description="Atur siapa yang bisa masuk, model yang tersedia, dan batas pemakaian mereka."
      />
      <div className="section__head">
        <Field label="Cari nama atau email">
          <input
            className="input"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </Field>
        <button className="button" onClick={() => setSelected('')}>
          + Tambah pengguna
        </button>
      </div>
      <Feedback error={users.error?.message ?? detail.error?.message} />
      {users.loading && <p role="status">Memuat pengguna…</p>}
      {users.data && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Pengguna</th>
                <th>Akses</th>
                <th>Status</th>
                <th>Saldo</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.data.map((u) => (
                <tr key={u.id} aria-selected={u.id === selected}>
                  <td>
                    <strong>{u.display_name}</strong>
                    <br />
                    <span className="muted">{u.email}</span>
                  </td>
                  <td>
                    {u.role} / {u.tier}
                  </td>
                  <td>
                    <span className="badge">{u.status}</span>
                  </td>
                  <td className="num money">{formatIDR(u.balance_idr)}</td>
                  <td>
                    <button className="button" onClick={() => setSelected(u.id)}>
                      Kelola
                    </button>
                  </td>
                </tr>
              ))}
              {!users.data.length && (
                <tr>
                  <td colSpan={5}>Tidak ada pengguna yang cocok.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {!selected ? (
        <UserEditor key="new" user={null} onSaved={users.reload} />
      ) : detail.data && !detail.loading ? (
        <UserEditor
          key={detail.data.id + JSON.stringify(detail.data)}
          user={detail.data}
          onSaved={() => {
            users.reload()
            detail.reload()
          }}
        />
      ) : (
        <p role="status">Memuat detail…</p>
      )}
    </div>
  )
}
