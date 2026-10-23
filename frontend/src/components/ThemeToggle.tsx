import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark' | 'system'
function savedTheme(): Theme {
  try {
    const v = localStorage.getItem('atheena.theme')
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}
function applyTheme(theme: Theme) {
  const dark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
}
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(savedTheme)
  useEffect(() => {
    applyTheme(theme)
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    const update = () => applyTheme(theme)
    media?.addEventListener('change', update)
    return () => media?.removeEventListener('change', update)
  }, [theme])
  function change(value: Theme) {
    setTheme(value)
    try {
      localStorage.setItem('atheena.theme', value)
    } catch {
      /* Private browsing can block storage. */
    }
    applyTheme(value)
  }
  return (
    <label className="theme-control">
      <span aria-hidden="true">◐</span>
      <span className="visually-hidden">Tema</span>
      <select aria-label="Tema" value={theme} onChange={(e) => change(e.target.value as Theme)}>
        <option value="system">Ikuti perangkat</option>
        <option value="light">Terang</option>
        <option value="dark">Gelap</option>
      </select>
    </label>
  )
}
