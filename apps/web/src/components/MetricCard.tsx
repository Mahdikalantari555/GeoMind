import { Sparkline } from './Sparkline'

interface MetricCardProps {
  label: string
  value: string | number
  delta?: {
    value: string
    isPositive?: boolean
  }
  sparklineData?: number[]
  sparklineColor?: string
  icon?: React.ReactNode
  subtitle?: string
  className?: string
}

export function MetricCard({
  label,
  value,
  delta,
  sparklineData,
  sparklineColor = 'var(--gf-accent)',
  icon,
  subtitle,
  className = '',
}: MetricCardProps) {
  return (
    <div
      data-testid={`metric-card-${label.toLowerCase().replace(/\s+/g, '-')}`}
      className={`relative overflow-hidden rounded-xl border border-gf-border bg-gf-panel p-4 shadow-xs transition-shadow hover:shadow-sm ${className}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1">
          <p className="text-xs font-medium tracking-wide text-gf-muted uppercase">{label}</p>
          <div className="flex items-baseline gap-2">
            <span className="font-tabular text-2xl font-semibold tracking-tight text-gf-text">{value}</span>
            {delta && (
              <span
                className={`inline-flex items-center rounded-full px-1.5 py-0.5 font-tabular text-[10px] font-medium ${
                  delta.isPositive !== false
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
                    : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
                }`}
              >
                {delta.value}
              </span>
            )}
          </div>
          {subtitle && <p className="text-xs text-gf-muted">{subtitle}</p>}
        </div>
        {icon && (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-gf-border/60 bg-gf-bg text-gf-muted">
            {icon}
          </div>
        )}
      </div>

      {sparklineData && sparklineData.length > 1 && (
        <div className="mt-3 flex justify-end">
          <Sparkline data={sparklineData} color={sparklineColor} width={110} height={28} />
        </div>
      )}
    </div>
  )
}
