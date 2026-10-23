import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { Shell } from './components/Shell'
import { ErrorPage, InactivePage, SignedOutPage } from './pages/StatusPages'
import { SessionProvider } from './session'
import { useSession } from './session-context'

// Route-level code splitting: the chart library only loads with the overview page.
const OverviewPage = lazy(() =>
  import('./pages/Overview').then((m) => ({ default: m.OverviewPage })),
)
const KeysPage = lazy(() => import('./pages/Keys').then((m) => ({ default: m.KeysPage })))
const QuickstartPage = lazy(() =>
  import('./pages/Quickstart').then((m) => ({ default: m.QuickstartPage })),
)
const TopUpPage = lazy(() => import('./pages/TopUp').then((m) => ({ default: m.TopUpPage })))
const ProfilePage = lazy(() => import('./pages/Profile').then((m) => ({ default: m.ProfilePage })))
const AdminBalancePage = lazy(() =>
  import('./pages/AdminBalance').then((m) => ({ default: m.AdminBalancePage })),
)
const UsersPage = lazy(() => import('./pages/admin/Users').then((m) => ({ default: m.UsersPage })))
const ModelsPage = lazy(() =>
  import('./pages/admin/Models').then((m) => ({ default: m.ModelsPage })),
)
const UsagePage = lazy(() => import('./pages/admin/Usage').then((m) => ({ default: m.UsagePage })))
const SettingsPage = lazy(() =>
  import('./pages/admin/Settings').then((m) => ({ default: m.SettingsPage })),
)
const AuditPage = lazy(() => import('./pages/admin/Audit').then((m) => ({ default: m.AuditPage })))
const StatusPage = lazy(() =>
  import('./pages/admin/Status').then((m) => ({ default: m.StatusPage })),
)
const LeaderboardPage = lazy(() =>
  import('./pages/Leaderboard').then((m) => ({ default: m.LeaderboardPage })),
)
const PricingPage = lazy(() => import('./pages/Pricing').then((m) => ({ default: m.PricingPage })))

function Routed() {
  const { state } = useSession()
  if (state.status === 'loading') return <div className="status-page muted">Memuat…</div>
  if (state.status === 'inactive') return <InactivePage />
  if (state.status === 'signed-out') return <SignedOutPage />
  if (state.status === 'error') return <ErrorPage message={state.message} />

  const isAdmin = state.me.role === 'admin'
  return (
    <Suspense fallback={<div className="status-page muted">Memuat…</div>}>
      <Routes>
        <Route path="/app" element={<Shell />}>
          <Route index element={<OverviewPage />} />
          <Route path="keys" element={<KeysPage />} />
          <Route path="mulai" element={<QuickstartPage />} />
          <Route path="topup" element={<TopUpPage />} />
          <Route path="profil" element={<ProfilePage />} />
          <Route path="leaderboard" element={<LeaderboardPage />} />
          <Route path="paket" element={<PricingPage workspace />} />
          {isAdmin && <Route path="admin/saldo" element={<AdminBalancePage />} />}
          {isAdmin && (
            <>
              <Route path="admin/users" element={<UsersPage />} />
              <Route path="admin/models" element={<ModelsPage />} />
              <Route path="admin/usage" element={<UsagePage />} />
              <Route path="admin/settings" element={<SettingsPage />} />
              <Route path="admin/audit" element={<AuditPage />} />
              <Route path="admin/status" element={<StatusPage />} />
            </>
          )}
          <Route path="*" element={<Navigate to="/app" replace />} />
        </Route>
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="status-page">Memuat…</div>}>
        <Routes>
          <Route path="/pricing" element={<PricingPage />} />
          <Route
            path="*"
            element={
              <SessionProvider>
                <Routed />
              </SessionProvider>
            }
          />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
