import { Link, NavLink, Outlet } from 'react-router'
import { formatIDR, formatNumber } from '../format'
import { useMe } from '../session-context'
import { ThemeToggle } from './ThemeToggle'
import { getSurface, siteLinks } from '../sites'

export function Shell() {
  const { me } = useMe()
  const low = me.balance_idr < me.low_balance_threshold_idr
  const surface = getSurface()
  const links = siteLinks(surface)
  const consoleOnly = surface === 'console'

  return (
    <div className="shell">
      <a className="skip-link" href="#konten">
        Langsung ke konten
      </a>
      <aside className="rail">
        <div className="rail__top">
          <a className="wordmark" href={links.home}>
            <img src="/brand/mark.svg" alt="" width="25" height="28" /> ATHEENA
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
          {!consoleOnly && (
            <>
              <NavLink to="/app" end>
                Ringkasan
              </NavLink>
              <NavLink to="/app/keys">API key</NavLink>
              <NavLink to="/app/paket">Paket & kalkulator</NavLink>
              <NavLink to="/app/mulai">Mulai</NavLink>
              <NavLink to="/app/topup">Top-up</NavLink>
              <NavLink to="/app/leaderboard">Leaderboard</NavLink>
              <NavLink to="/app/profil">Pengaturan</NavLink>
            </>
          )}
          {consoleOnly && <a href={links.dashboard}>Dashboard pengguna ↗</a>}
          {me.role === 'admin' && surface === 'dashboard' && (
            <a href={links.console}>Console admin ↗</a>
          )}
          {me.role === 'admin' && surface !== 'dashboard' && (
            <>
              <p className="nav__group">Admin</p>
              <NavLink to="/app/admin/users">Pengguna</NavLink>
              <NavLink to="/app/admin/saldo">Saldo pengguna</NavLink>
              <NavLink to="/app/admin/usage">Pemakaian global</NavLink>
              <NavLink to="/app/admin/models">Katalog & harga</NavLink>
              <NavLink to="/app/admin/settings">Pengaturan gateway</NavLink>
              <NavLink to="/app/admin/audit">Audit log</NavLink>
              <NavLink to="/app/admin/status">Status sistem</NavLink>
            </>
          )}
        </nav>
        <p className="rail__user">
          <span className="badge">
            {me.role} / {me.tier}
          </span>
          <br />@{me.username}
          <br />
          {me.email}
        </p>
        <ThemeToggle />
      </aside>
      <main className="main" id="konten" tabIndex={-1}>
        {low && !consoleOnly && (
          <p className="banner" role="status">
            Saldo Anda {formatIDR(me.balance_idr)}, di bawah batas peringatan{' '}
            {formatIDR(me.low_balance_threshold_idr)}. Request ditolak saat saldo di bawah minimum.{' '}
            <Link to="/app/topup">Top-up sekarang</Link>
          </p>
        )}
        <Outlet />
        <footer className="workspace-footer">
          <span>ATHEENA © 2026 · Kecerdasan dengan arah.</span>
          <a href={links.pricing}>Paket & model ↗</a>
        </footer>
      </main>
    </div>
  )
}
