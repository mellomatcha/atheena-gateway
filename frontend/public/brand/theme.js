;(() => {
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  function current() {
    try {
      return localStorage.getItem('atheena.theme') || 'system'
    } catch {
      return 'system'
    }
  }
  function apply() {
    const setting = current()
    document.documentElement.dataset.theme =
      setting === 'dark' || (setting === 'system' && media.matches) ? 'dark' : 'light'
    const select = document.querySelector('[data-theme-select]')
    if (select) select.value = setting
  }
  apply()
  media.addEventListener('change', apply)
  window.addEventListener('storage', apply)
  document.addEventListener('DOMContentLoaded', () => {
    apply()
    document.querySelector('[data-theme-select]')?.addEventListener('change', (event) => {
      try {
        localStorage.setItem('atheena.theme', event.target.value)
      } catch {
        /* Preference may not persist. */
      }
      document.documentElement.dataset.theme =
        event.target.value === 'dark' || (event.target.value === 'system' && media.matches)
          ? 'dark'
          : 'light'
    })
  })
})()
