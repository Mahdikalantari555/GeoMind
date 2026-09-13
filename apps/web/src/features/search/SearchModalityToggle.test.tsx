import '@/i18n'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { SearchModalityToggle } from './SearchModalityToggle'

describe('SearchModalityToggle', () => {
  it('defaults to text modality', () => {
    const onChange = vi.fn()
    render(<SearchModalityToggle modalities="text" onChange={onChange} />)
    expect(screen.getByTestId('modality-text')).toHaveClass('bg-gf-accent', 'text-white')
    expect(screen.getByTestId('modality-image')).not.toHaveClass('bg-gf-accent')
    expect(screen.getByTestId('modality-both')).not.toHaveClass('bg-gf-accent')
  })

  it('clicking image sets modalities to image', () => {
    const onChange = vi.fn()
    render(<SearchModalityToggle modalities="text" onChange={onChange} />)
    fireEvent.click(screen.getByTestId('modality-image'))
    expect(onChange).toHaveBeenCalledWith('image')
  })

  it('clicking both sets modalities to both', () => {
    const onChange = vi.fn()
    render(<SearchModalityToggle modalities="text" onChange={onChange} />)
    fireEvent.click(screen.getByTestId('modality-both'))
    expect(onChange).toHaveBeenCalledWith('both')
  })

  it('renders correct label for each modality', () => {
    const onChange = vi.fn()
    render(<SearchModalityToggle modalities="image" onChange={onChange} />)
    expect(screen.getByTestId('modality-text').textContent).toBe('Text')
    expect(screen.getByTestId('modality-image').textContent).toBe('Image')
    expect(screen.getByTestId('modality-both').textContent).toBe('Both')
  })

  it('shows image button as active when modalities=image', () => {
    const onChange = vi.fn()
    render(<SearchModalityToggle modalities="image" onChange={onChange} />)
    expect(screen.getByTestId('modality-image')).toHaveClass('bg-gf-accent', 'text-white')
  })

  it('shows both button as active when modalities=both', () => {
    const onChange = vi.fn()
    render(<SearchModalityToggle modalities="both" onChange={onChange} />)
    expect(screen.getByTestId('modality-both')).toHaveClass('bg-gf-accent', 'text-white')
  })
})
