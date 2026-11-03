type Props = { className?: string }

export function Skeleton({ className = '' }: Props) {
  return (
    <div
      data-testid="skeleton"
      className={`animate-pulse rounded-md bg-gf-border/40 ${className}`}
      aria-hidden="true"
    />
  )
}
