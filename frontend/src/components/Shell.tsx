import { NavLink, Outlet } from 'react-router'
import { formatNumber } from '../format'
import { useMe } from '../session-context'

export function Shell() {
  const { me } = useMe()
  const low = me.balance_idr < me.low_balance_threshold_idr

  return (
    <div className="shell">
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
          <NavLink to="/app/topup">Top-up</NavLink>
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
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
