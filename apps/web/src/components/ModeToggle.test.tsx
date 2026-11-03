import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ModeToggle } from './ModeToggle'

describe('ModeToggle', () => {
  beforeEach(() => localStorage.clear())
  it('toggles and persists', () => {
    render(<ModeToggle />)
    const btn = screen.getByTestId('mode-toggle')
    expect(btn.textContent).toBe('Simple')
    fireEvent.click(btn)
    expect(btn.textContent).toBe('Advanced')
    expect(localStorage.getItem('gf.mode')).toBe('advanced')
  })
})
