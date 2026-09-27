import '@/i18n'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { IngestPage } from './IngestPage'
import { ingestApi, jobsApi } from '@/api/knowledge'

vi.mock('@/features/workspace/hooks', () => ({
  useWorkspace: () => ({
    data: { status: 'open', path: '/test/ws', settings: {} },
    isLoading: false,
  }),
}))

vi.mock('./hooks', () => ({
  useCollections: () => ({
    data: [{ id: 'col-1', name: 'Default Collection' }],
    isLoading: false,
  }),
  useIngest: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useJobPolling: () => ({
    data: null,
    refetch: vi.fn(),
  }),
}))

vi.mock('@/api/knowledge', () => ({
  ingestApi: {
    file: vi.fn(),
  },
  jobsApi: {
    get: vi.fn(),
  },
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <IngestPage />
    </QueryClientProvider>
  )
}

describe('IngestPage', () => {
  it('renders ingest dropzone with multiple file input enabled', () => {
    const { container } = renderPage()
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    expect(input).toBeInTheDocument()
    expect(input.multiple).toBe(true)
  })

  it('handles batch file upload when multiple files are dropped', async () => {
    vi.mocked(ingestApi.file)
      .mockResolvedValueOnce({ job_id: 'job-1', status: 'accepted' })
      .mockResolvedValueOnce({ job_id: 'job-2', status: 'accepted' })

    vi.mocked(jobsApi.get)
      .mockResolvedValueOnce({ id: 'job-1', type: 'ingestion', status: 'completed', progress: 1, result: { segment_count: 5 } })
      .mockResolvedValueOnce({ id: 'job-2', type: 'ingestion', status: 'completed', progress: 1, result: { skipped: true, reason: 'duplicate' } })

    renderPage()

    const dropzone = screen.getByTestId('ingest-dropzone')
    const file1 = new File(['content 1'], 'file1.txt', { type: 'text/plain' })
    const file2 = new File(['content 2'], 'file2.txt', { type: 'text/plain' })

    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file1, file2],
      },
    })

    await waitFor(() => {
      expect(screen.getByTestId('ingest-batch')).toBeInTheDocument()
    })

    expect(screen.getByText('file1.txt')).toBeInTheDocument()
    expect(screen.getByText('file2.txt')).toBeInTheDocument()
  })
})
