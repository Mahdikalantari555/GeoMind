import '@/i18n'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SetupModal } from './SetupModal'

vi.mock('@/api/environment', () => ({
  environmentApi: {
    setOverrides: vi.fn().mockResolvedValue({ applied: {}, ignored: [] }),
  },
}))

vi.mock('./hooks', () => ({
  useCreateWorkspace: () => ({ mutateAsync: vi.fn().mockResolvedValue({ status: 'open' }), isPending: false }),
  useOpenWorkspace: () => ({ mutateAsync: vi.fn().mockResolvedValue({ status: 'open' }), isPending: false }),
  useUpdateSettings: () => ({ mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }),
  useWorkspaceSuggestions: () => ({ data: { root: '', suggestions: [] } }),
}))

function renderModal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SetupModal />
    </QueryClientProvider>,
  )
}

describe('SetupModal', () => {
  it('renders create and open tabs with compute config', () => {
    renderModal()

    expect(screen.getByText('Create new')).toBeInTheDocument()
    expect(screen.getByText('Open existing')).toBeInTheDocument()
    expect(screen.getByLabelText('LLM provider')).toBeInTheDocument()
    expect(screen.getByLabelText('Embedding backend')).toBeInTheDocument()
    expect(screen.getByLabelText('Hugging Face endpoint')).toBeInTheDocument()
    expect(screen.getByLabelText('Shared model cache root')).toBeInTheDocument()
  })

  it('switches between create and open tabs', () => {
    renderModal()

    fireEvent.click(screen.getByText('Open existing'))
    expect(screen.getByPlaceholderText('/path/to/workspace or parent directory')).toBeInTheDocument()
  })
})
