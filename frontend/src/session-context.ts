import { createContext, useContext } from 'react'
import type { Me } from './api'

export type SessionState =
  | { status: 'loading' }
  | { status: 'ready'; me: Me }
  | { status: 'inactive' }
  | { status: 'signed-out' }
  | { status: 'error'; message: string }

export interface SessionValue {
  state: SessionState
  refresh: () => Promise<void>
}

export const SessionContext = createContext<SessionValue | null>(null)

export function useSession(): SessionValue {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useSession must be used inside SessionProvider')
  return value
}

/** The signed-in member; only call inside routes rendered after the session is ready. */
export function useMe(): { me: Me; refresh: () => Promise<void> } {
  const { state, refresh } = useSession()
  if (state.status !== 'ready') throw new Error('session is not ready')
  return { me: state.me, refresh }
}
