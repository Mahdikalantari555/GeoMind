import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CommandPalette } from './CommandPalette'

describe('CommandPalette', () => {
  it('opens on Ctrl+K and navigates on Enter', () => {
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <CommandPalette />
        </MemoryRouter>
      </QueryClientProvider>
    )
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
    expect(screen.getByTestId('command-palette')).toBeInTheDocument()
    const input = screen.getByTestId('command-palette-input')
    fireEvent.change(input, { target: { value: 'Maps' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(screen.queryByTestId('command-palette')).not.toBeInTheDocument()
  })
  it('closes on Escape', () => {
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <CommandPalette />
        </MemoryRouter>
      </QueryClientProvider>
    )
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
    expect(screen.getByTestId('command-palette')).toBeInTheDocument()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByTestId('command-palette')).not.toBeInTheDocument()
  })
})
