import { useEffect, useRef, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { DayPoint } from '../api'
import { formatCompact, formatIDR, formatLongDay, formatNumber, formatShortDay } from '../format'

type Unit = 'idr' | 'token'

interface TooltipProps {
  active?: boolean
  payload?: { payload: DayPoint }[]
  unit: Unit
}

function DayTooltip({ active, payload, unit }: TooltipProps) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="chart-tip">
      <p>{formatLongDay(point.day)}</p>
      <p className="num chart-tip__value">
        {unit === 'idr' ? formatIDR(point.totals.cost_idr) : `${formatNumber(point.totals.tokens)} token`}
      </p>
      <p className="num muted">{formatNumber(point.totals.requests)} request</p>
    </div>
  )
}

// Roughly one x-axis label per this many pixels, so "11 Sep" labels never collide.
const PX_PER_TICK = 64

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}

export function UsageChart({ points, unit }: { points: DayPoint[]; unit: Unit }) {
  const [plotRef, width] = useWidth<HTMLDivElement>()
  const maxTicks = Math.max(2, Math.floor((width - 64) / PX_PER_TICK))
  const interval = points.length > maxTicks ? Math.ceil(points.length / maxTicks) - 1 : 0
  const total = points.reduce((sum, p) => sum + p.value, 0)
  const summary =
    unit === 'idr'
      ? `Total ${formatIDR(total)} selama ${points.length} hari.`
      : `Total ${formatNumber(total)} token selama ${points.length} hari.`

  return (
    <figure className="chart" aria-label="Grafik pemakaian per hari">
      <figcaption className="visually-hidden">
        {summary} Rincian per hari ada di tabel log di bawah.
      </figcaption>
      <div className="chart__plot" aria-hidden="true" ref={plotRef}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={points} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--gunmetal)" />
            <XAxis
              dataKey="day"
              tickFormatter={formatShortDay}
              interval={interval}
              tickLine={false}
              axisLine={{ stroke: 'var(--gunmetal)' }}
              tick={{ fill: 'var(--steel)', fontSize: 12 }}
            />
            <YAxis
              width={64}
              tickFormatter={(v: number) => formatCompact(v)}
              tickLine={false}
              axisLine={false}
              tick={{ fill: 'var(--steel)', fontSize: 12, fontFamily: 'var(--font-num)' }}
              allowDecimals={false}
            />
            <Tooltip
              cursor={{ fill: 'var(--graphite)' }}
              content={<DayTooltip unit={unit} />}
              isAnimationActive={false}
            />
            <Bar
              dataKey="value"
              fill="var(--steel)"
              activeBar={{ fill: 'var(--ice)' }}
              radius={[2, 2, 0, 0]}
              maxBarSize={28}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}
