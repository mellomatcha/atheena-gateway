export function getSurface(host = window.location.hostname) {
  if (host === 'console.atheena.online') return 'console'
  if (host === 'dashboard.atheena.online') return 'dashboard'
  if (host === 'atheena.online') return 'public'
  return 'local'
}

export function siteLinks(surface = getSurface()) {
  const deployed = surface !== 'local'
  return {
    home: deployed ? 'https://atheena.online/' : '/',
    pricing: deployed ? 'https://atheena.online/pricing' : '/pricing',
    dashboard: deployed ? 'https://dashboard.atheena.online/app' : '/app',
    console: deployed ? 'https://console.atheena.online/app/admin/users' : '/app/admin/users',
  }
}
