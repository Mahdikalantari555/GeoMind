interface SparklineProps {
  data: number[]
  width?: number
  height?: number
  color?: string
  fill?: boolean
  className?: string
}

export function Sparkline({
  data,
  width = 96,
  height = 32,
  color = 'var(--gf-accent)',
  fill = true,
  className = '',
}: SparklineProps) {
  if (!data || data.length < 2) {
    return <div style={{ width, height }} className={className} />
  }

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const padding = 2
  const innerHeight = height - padding * 2
  const innerWidth = width - padding * 2

  const points = data.map((val, idx) => {
    const x = padding + (idx / (data.length - 1)) * innerWidth
    const y = height - padding - ((val - min) / range) * innerHeight
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  const pathD = `M ${points.join(' L ')}`
  const fillD = `${pathD} L ${width - padding},${height} L ${padding},${height} Z`

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={`overflow-visible ${className}`}
      aria-hidden="true"
    >
      {fill && (
        <path
          d={fillD}
          fill={color}
          fillOpacity={0.12}
          stroke="none"
        />
      )}
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
