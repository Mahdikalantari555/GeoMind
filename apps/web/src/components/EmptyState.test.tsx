import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders CTA', () => {
    render(<EmptyState title="None" description="desc" action={<button>Do it</button>} />)
    expect(screen.getByTestId('empty-state')).toBeInTheDocument()
    expect(screen.getByText('Do it')).toBeInTheDocument()
  })
})
