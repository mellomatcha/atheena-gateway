import { useState } from 'react'

export function CopyButton({ text, label = 'Salin' }: { text: string; label?: string }) {
  const [state, setState] = useState<'idle' | 'done' | 'failed'>('idle')

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setState('done')
    } catch {
      setState('failed')
    }
    window.setTimeout(() => setState('idle'), 2000)
  }

  return (
    <button type="button" className="button button--small" onClick={() => void copy()}>
      <span aria-live="polite">
        {state === 'done' ? 'Tersalin' : state === 'failed' ? 'Salin manual' : label}
      </span>
    </button>
  )
}

export function CodeBlock({ code, label }: { code: string; label: string }) {
  return (
    <div className="code">
      <div className="code__bar">
        <span className="muted">{label}</span>
        <CopyButton text={code} />
      </div>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  )
}
