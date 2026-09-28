import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { Shell } from './components/Shell'
import { AdminBalancePage } from './pages/AdminBalance'
import { ErrorPage, InactivePage, SignedOutPage } from './pages/StatusPages'
import { TopUpPage } from './pages/TopUp'
import { SessionProvider } from './session'
import { useSession } from './session-context'

function Routed() {
  const { state } = useSession()
  if (state.status === 'loading') return <div className="status-page muted">Memuat…</div>
  if (state.status === 'inactive') return <InactivePage />
  if (state.status === 'signed-out') return <SignedOutPage />
  if (state.status === 'error') return <ErrorPage message={state.message} />

  const isAdmin = state.me.role === 'admin'
  return (
    <Routes>
      <Route path="/app" element={<Shell />}>
        <Route index element={<Navigate to="/app/topup" replace />} />
        <Route path="topup" element={<TopUpPage />} />
        {isAdmin && <Route path="admin/saldo" element={<AdminBalancePage />} />}
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <Routed />
      </SessionProvider>
    </BrowserRouter>
  )
}
