import type { ReactNode } from 'react'

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      {children}
    </label>
  )
}
export function Feedback({ error, success }: { error?: string | null; success?: string | null }) {
  return (
    <>
      {error && (
        <p className="notice notice--error" role="alert">
          {error}
        </p>
      )}
      {success && (
        <p className="notice notice--ok" role="status">
          {success}
        </p>
      )}
    </>
  )
}
export function PageHead({ title, description }: { title: string; description: string }) {
  return (
    <header className="page__head">
      <span className="eyebrow">ATHEENA / WORKSPACE</span>
      <h1>{title}</h1>
      <p className="muted">{description}</p>
    </header>
  )
}
