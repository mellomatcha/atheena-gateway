import { api } from '../../api'
import { Feedback, PageHead } from '../../components/AdminUI'
import { formatMs, formatNumber } from '../../format'
import { useAsync } from '../../useAsync'

interface Health {
  upstream_ok: boolean
  upstream_error: string | null
  upstream_latency_ms: number | null
  active_streams: number
  requests_last_hour: number
  failed_last_hour: number
  upstream_failed_last_hour: number
  error_rate_last_hour: number
  avg_latency_ms_last_hour: number | null
  p95_latency_ms_last_hour: number | null
}
export function StatusPage() {
  const health = useAsync('health', () => api<Health>('/admin/health'))
  const h = health.data
  return (
    <div className="page">
      <PageHead
        title="Status sistem"
        description="Koneksi 9Router dan kualitas request dalam satu jam terakhir."
      />
      <div className="actions">
        <button className="button" disabled={health.loading} onClick={health.reload}>
          {health.loading ? 'Memeriksa…' : 'Periksa sekarang'}
        </button>
      </div>
      <Feedback error={health.error?.message} />
      {h && (
        <>
          <section
            className={`panel editor health-card ${h.upstream_ok ? '' : 'health-card--error'}`}
          >
            <span className="eyebrow">KONEKSI PROVIDER</span>
            <h2>{h.upstream_ok ? '9Router terhubung' : '9Router tidak terjangkau'}</h2>
            <p>
              {h.upstream_ok
                ? `Pemeriksaan selesai dalam ${formatMs(h.upstream_latency_ms)}.`
                : h.upstream_error}
            </p>
          </section>
          <dl className="stats">
            {[
              ['Stream aktif', formatNumber(h.active_streams)],
              ['Request / 1 jam', formatNumber(h.requests_last_hour)],
              ['Request gagal', formatNumber(h.failed_last_hour)],
              ['Tingkat error', `${(h.error_rate_last_hour * 100).toFixed(1)}%`],
              ['Latensi rata-rata', formatMs(h.avg_latency_ms_last_hour)],
              ['Latensi p95', formatMs(h.p95_latency_ms_last_hour)],
            ].map(([label, value]) => (
              <div className="stat" key={label}>
                <dt className="stat__label">{label}</dt>
                <dd className="stat__value num">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="muted">
            {h.upstream_failed_last_hour} request gagal di sisi provider. Latensi dihitung dari
            request yang selesai; data diperbarui saat halaman dibuka atau diperiksa ulang.
          </p>
        </>
      )}
    </div>
  )
}
