import '@/i18n'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { QAResult } from '@/api/search'
import { AskPage } from './AskPage'

vi.mock('@/api/search', async (orig) => {
  const actual = await orig<typeof import('@/api/search')>()
  return {
    ...actual,
    askApi: { ask: vi.fn() },
    searchApi: { run: vi.fn() },
  }
})

vi.mock('@/api/ops', () => ({
  opsApi: { suggestCorrection: vi.fn() },
}))

vi.mock('@/features/workspace/hooks', () => ({
  useWorkspace: () => ({ data: { status: 'open' } }),
}))

const { askApi } = await import('@/api/search')

const abstained: QAResult = {
  text: 'not found in selected sources',
  citations: [],
  abstained: true,
  abstention_reason: 'No LLM backend available',
  sources: [],
  retrieval_run_id: 'run_1',
  latency_ms: 5,
  model: 'none',
}

const answered: QAResult = {
  text: 'NDVI declines under water stress.',
  citations: [
    {
      id: 'cit_1',
      answer_id: 'ans_1',
      segment_id: 'seg_abc1234567890',
      locator: { path: 'research/crop_health.pdf' },
      claim_span: null,
    },
  ],
  abstained: false,
  abstention_reason: null,
  sources: [
    {
      id: 'seg_abc1234567890',
      score: 0.9,
      sparse_score: 0.8,
      dense_score: 0.95,
      metadata: {},
      text: 'NDVI drops under stress.',
      locator: { path: 'research/crop_health.pdf' },
    },
  ],
  retrieval_run_id: 'run_2',
  latency_ms: 40,
  model: 'recall',
  turn_id: 'turn_test123',
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AskPage />
    </QueryClientProvider>
  )
}

describe('AskPage', () => {
  it('renders unified search and QA workbench', () => {
    renderPage()
    expect(screen.getByTestId('unified-recall-qa')).toBeInTheDocument()
    expect(screen.getByTestId('ask-form')).toBeInTheDocument()
  })

  it('shows the abstention banner when context is insufficient', async () => {
    vi.mocked(askApi.ask).mockResolvedValue(abstained)
    renderPage()

    // Switch to Grounded QA to test LLM abstention banner
    const qaBtn = screen.getByText('Grounded QA')
    fireEvent.click(qaBtn)

    const input = screen.getByPlaceholderText(/Ask a remote sensing question/i)
    fireEvent.change(input, { target: { value: 'what about ndvi?' } })
    fireEvent.submit(screen.getByTestId('ask-form'))

    await waitFor(() => {
      expect(screen.getByTestId('abstention-banner')).toBeInTheDocument()
    })
    expect(screen.getByText('No LLM backend available')).toBeInTheDocument()
  })

  it('shows answer with citations and opens the provenance drawer', async () => {
    vi.mocked(askApi.ask).mockResolvedValue(answered)
    renderPage()

    const qaBtn = screen.getByText('Grounded QA')
    fireEvent.click(qaBtn)

    const input = screen.getByPlaceholderText(/Ask a remote sensing question/i)
    fireEvent.change(input, { target: { value: 'ndvi trend?' } })
    fireEvent.submit(screen.getByTestId('ask-form'))

    await waitFor(() => {
      expect(screen.getByText('NDVI declines under water stress.')).toBeInTheDocument()
    })

    const inspectBtn = screen.getByText(/Inspect Provenance/i)
    fireEvent.click(inspectBtn)

    expect(screen.getByTestId('provenance-drawer')).toBeInTheDocument()
    expect(screen.getByText(/Provenance & Evidence/i)).toBeInTheDocument()
  })

  it('toggles between fast recall and grounded QA modes', () => {
    renderPage()
    const recallBtn = screen.getByText(/Fast Recall/i)
    const qaBtn = screen.getByText(/Grounded QA/i)

    expect(recallBtn).toBeInTheDocument()
    expect(qaBtn).toBeInTheDocument()

    fireEvent.click(qaBtn)
    expect(qaBtn).toHaveClass('bg-gf-accent')
  })
})
