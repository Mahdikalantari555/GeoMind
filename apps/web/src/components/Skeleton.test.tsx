import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Skeleton } from './Skeleton'

describe('Skeleton', () => {
  it('renders', () => {
    render(<Skeleton className="h-4 w-10" />)
    expect(screen.getByTestId('skeleton')).toBeInTheDocument()
  })
})
