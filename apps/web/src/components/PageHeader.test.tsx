import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PageHeader } from './PageHeader'

describe('PageHeader', () => {
  it('renders title', () => {
    render(<PageHeader title="Hello" subtitle="sub" />)
    expect(screen.getByTestId('page-header')).toBeInTheDocument()
    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(screen.getByText('sub')).toBeInTheDocument()
  })
})
