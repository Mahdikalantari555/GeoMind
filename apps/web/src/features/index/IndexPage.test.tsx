import '@/i18n'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { IndexPage } from './IndexPage'
import { opsApi } from '@/api/ops'

vi.mock('@/api/ops', () => ({
  opsApi: {
    getIndexManifest: vi.fn().mockResolvedValue({
      space_id: 'text.onnx.Xenova-all-MiniLM-L6-v2.v1',
      manifest: {
        space_id: 'text.onnx.Xenova-all-MiniLM-L6-v2.v1',
        model_id: 'Xenova/all-MiniLM-L6-v2',
        dimension: 384,
        doc_count: 42,
      },
      exists: true,
    }),
    buildIndex: vi.fn().mockResolvedValue({
      status: 'built',
      space_id: 'text.onnx.Xenova-all-MiniLM-L6-v2.v1',
    }),
    rebuildIndex: vi.fn().mockResolvedValue({
      status: 'rebuilt',
      space_id: 'text.onnx.Xenova-all-MiniLM-L6-v2.v1',
    }),
  },
}))

vi.mock('../workspace/modelHooks', () => ({
  useModels: () => ({ data: [] }),
  useDownloadModel: () => ({ mutate: vi.fn(), isPending: false }),
  formatBytes: () => '10 MB',
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <IndexPage />
    </QueryClientProvider>,
  )
}

describe('IndexPage', () => {
  it('renders manifest information and triggers build with active space', async () => {
    renderPage()

    // Wait for manifest data to appear
    expect(await screen.findByTestId('index-vector-count')).toHaveTextContent('42')
    expect(screen.getByTestId('index-active-space')).toHaveTextContent(
      'text.onnx.Xenova-all-MiniLM-L6-v2.v1',
    )
    expect(screen.getByTestId('index-dimension')).toHaveTextContent('384')
    expect(screen.getByTestId('index-model-id')).toHaveTextContent('Xenova/all-MiniLM-L6-v2')

    // Click build index button
    const buildBtn = screen.getByTestId('build-index-btn')
    fireEvent.click(buildBtn)
    await waitFor(() => {
      expect(opsApi.buildIndex).toHaveBeenCalledWith(undefined)
    })

    // Click rebuild index button
    const rebuildBtn = screen.getByTestId('rebuild-index-btn')
    fireEvent.click(rebuildBtn)
    await waitFor(() => {
      expect(opsApi.rebuildIndex).toHaveBeenCalledWith(undefined)
    })
  })
})
