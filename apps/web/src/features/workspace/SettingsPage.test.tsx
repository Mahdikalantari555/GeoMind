import '@/i18n'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SettingsPage } from './SettingsPage'

const settings = {
  name: 'Test WS',
  language: null,
  offline: false,
  model_path: null,
  embedding_path: null,
  vision_path: null,
  default_collection: null,
  index_dir: 'indexes',
  objects_dir: 'objects',
  logs_dir: 'logs',
  batch_size: 64,
  thread_count: 4,
  llm_provider: 'api',
  llm_api_base_url: null,
  llm_api_key_env: 'GEOMEMORY_LLM_API_KEY',
  llm_model_id: 'kilo-auto/free',
  llm_context_window: 32768,
  embedding_backend: 'onnx',
  st_model_name: 'sentence-transformers/all-MiniLM-L6-v2',
  onnx_model_name: 'Xenova/all-MiniLM-L6-v2',
  vector_backend: 'sqlite-vec',
  qdrant_url: null,
  qdrant_api_key: null,
  pdf_parser: 'auto',
}

vi.mock('./hooks', () => ({
  useWorkspace: () => ({ data: { status: 'open', settings } }),
}))

vi.mock('./modelHooks', () => ({
  useUpdateSettings: () => ({
    mutateAsync: vi.fn().mockResolvedValue({}),
    mutate: vi.fn((_body: unknown, opts?: { onSuccess?: () => void }) => {
      opts?.onSuccess?.()
    }),
    isPending: false,
  }),
  useVisionDownloadModel: () => ({ mutate: vi.fn(), isPending: false }),
  useModels: () => ({ data: [] }),
  useDownloadModel: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/features/knowledge/hooks', () => ({
  useJobPolling: () => ({ data: null }),
}))

vi.mock('@/api/environment', () => ({
  environmentApi: {
    setOverrides: vi.fn().mockResolvedValue({ applied: {}, ignored: [] }),
  },
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SettingsPage />
    </QueryClientProvider>,
  )
}

describe('SettingsPage', () => {
  it('renders without GGUF path labels', () => {
    renderPage()
    expect(screen.queryByText(/GGUF path/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/LLM GGUF path/i)).not.toBeInTheDocument()
  })

  it('renders free-text model download input and scan button', () => {
    renderPage()
    expect(screen.getByTestId('custom-model-input')).toBeInTheDocument()
    expect(screen.getByTestId('custom-model-download-btn')).toBeInTheDocument()
    expect(screen.getByTestId('scan-models-btn')).toBeInTheDocument()
  })

  it('triggers model download with custom repo id', () => {
    renderPage()
    const input = screen.getByTestId('custom-model-input')
    const btn = screen.getByTestId('custom-model-download-btn')

    fireEvent.change(input, { target: { value: 'BAAI/bge-small-en-v1.5' } })
    fireEvent.click(btn)

    expect(screen.getByTestId('custom-model-input')).toHaveValue('')
  })
})