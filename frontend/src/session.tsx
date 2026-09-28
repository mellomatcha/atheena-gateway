import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, type Me } from './api'
import { SessionContext, type SessionState } from './session-context'

async function loadSession(): Promise<SessionState> {
  try {
    return { status: 'ready', me: await api<Me>('/me') }
  } catch (error) {
    if (error instanceof ApiError && error.code === 'account_inactive') return { status: 'inactive' }
    if (error instanceof ApiError && error.status === 401) return { status: 'signed-out' }
    return { status: 'error', message: (error as Error).message }
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: 'loading' })

  const refresh = useCallback(async () => {
    setState(await loadSession())
  }, [])

  useEffect(() => {
    let active = true
    void loadSession().then((next) => {
      if (active) setState(next)
    })
    return () => {
      active = false
    }
  }, [])

  return <SessionContext value={{ state, refresh }}>{children}</SessionContext>
}
