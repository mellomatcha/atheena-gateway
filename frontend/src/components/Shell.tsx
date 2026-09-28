import { Link, NavLink, Outlet } from 'react-router'
import { formatIDR, formatNumber } from '../format'
import { useMe } from '../session-context'

export function Shell() {
  const { me } = useMe()
  const low = me.balance_idr < me.low_balance_threshold_idr

  return (
    <div className="shell">
      <a className="skip-link" href="#konten">
        Langsung ke konten
      </a>
      <aside className="rail">
        <div className="rail__top">
          <a className="wordmark" href="/app">
            Atheena
          </a>
          <div className="readout">
            <span className="readout__label">Saldo</span>
            <span className="readout__value num" data-low={low}>
              <span className="readout__currency">{me.balance_idr < 0 ? '−Rp' : 'Rp'}</span>
              {formatNumber(Math.abs(me.balance_idr))}
            </span>
          </div>
        </div>
        <nav className="nav" aria-label="Menu utama">
          <NavLink to="/app" end>
            Ringkasan
          </NavLink>
          <NavLink to="/app/keys">API key</NavLink>
          <NavLink to="/app/mulai">Mulai</NavLink>
          <NavLink to="/app/topup">Top-up</NavLink>
          <NavLink to="/app/profil">Pengaturan</NavLink>
          {me.role === 'admin' && (
            <>
              <p className="nav__group">Admin</p>
              <NavLink to="/app/admin/saldo">Saldo pengguna</NavLink>
            </>
          )}
        </nav>
        <p className="rail__user">
          {me.display_name}
          <br />
          {me.email}
        </p>
      </aside>
      <main className="main" id="konten" tabIndex={-1}>
        {low && (
          <p className="banner" role="status">
            Saldo Anda {formatIDR(me.balance_idr)}, di bawah batas peringatan{' '}
            {formatIDR(me.low_balance_threshold_idr)}. Request ditolak saat saldo di bawah minimum.{' '}
            <Link to="/app/topup">Top-up sekarang</Link>
          </p>
        )}
        <Outlet />
      </main>
    </div>
  )
}
