import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ThemeToggle } from './ThemeToggle'

describe('ThemeToggle', () => {
  it('renders theme toggle button', () => {
    render(<ThemeToggle />)
    const btn = screen.getByTestId('theme-toggle')
    expect(btn).toBeInTheDocument()
  })

  it('switches between light and dark modes on click', () => {
    render(<ThemeToggle />)
    const btn = screen.getByTestId('theme-toggle')
    expect(btn.getAttribute('title')).toContain('Switch to dark mode')

    fireEvent.click(btn)
    expect(btn.getAttribute('title')).toContain('Switch to light mode')
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    fireEvent.click(btn)
    expect(btn.getAttribute('title')).toContain('Switch to dark mode')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })
})
