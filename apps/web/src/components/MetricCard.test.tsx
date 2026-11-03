import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MetricCard } from './MetricCard'

describe('MetricCard', () => {
  it('renders label and value', () => {
    render(<MetricCard label="Indexed Assets" value={42} />)
    expect(screen.getByText('Indexed Assets')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders positive delta pill', () => {
    render(
      <MetricCard
        label="Vectors"
        value={1200}
        delta={{ value: '+12% this week', isPositive: true }}
      />
    )
    expect(screen.getByText('+12% this week')).toBeInTheDocument()
  })

  it('renders sparkline when data is provided', () => {
    const { container } = render(
      <MetricCard
        label="Storage"
        value="120 MB"
        sparklineData={[10, 20, 15, 30, 45]}
      />
    )
    expect(container.querySelector('svg')).toBeInTheDocument()
  })
})
