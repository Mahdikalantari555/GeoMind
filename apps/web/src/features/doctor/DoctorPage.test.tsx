import '@/i18n'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DoctorPage } from './DoctorPage'

vi.mock('./hooks', () => ({
  useDoctor: () => ({
    data: {
      environment: {
        python_version: '3.12.0',
        python_ok: true,
        core_deps: { pydantic: true, numpy: true, click: true, yaml: true },
        core_ok: true,
        optional_deps: {
          Pillow: true,
          PyMuPDF: true,
          python_docx: true,
          rasterio: true,
          shapely: true,
          geopandas: true,
          onnxruntime: true,
          huggingface_hub: true,
          sqlite_vec: true,
          qdrant_client: false,
        },
      },
      workspace: { ok: false, closed: true, checks: { status: 'no workspace open' } },
      workspace_open: { ok: false, closed: true, checks: { open: false } },
      embedding: { hub_count: 1, downloaded: 1, active_backend: 'onnx', active_model: 'Xenova/all-MiniLM-L6-v2' },
      resolved_workspace_root: '/workspace',
      diagnostics: {
        llm: { provider: 'api', key_env: 'GEOMEMORY_LLM_API_KEY', key_configured: true, base_url: 'https://api.kilo.ai/api/gateway/v1', model_id: 'kilo-auto/free', context_window: 32768 },
        qdrant: { client_installed: false, url: null, reachable: false },
        pdf_parser: { resolved: 'pymupdf', opendataloader_installed: false, java_available: false },
        vision: { torch_installed: false, checkpoint_exists: false, model_available: false, download_status: 'missing' },
        embedding: { hub_count: 1, downloaded: 1, active_backend: 'onnx', active_model: 'Xenova/all-MiniLM-L6-v2', active_space_id: 'text.onnx.xenova-all-minilm-l6-v2.v1', model_available: true },
        sqlite_vec: { installed: true, loadable: true, version: '0.1.9' },
      },
    },
    isLoading: false,
    error: null,
  }),
  useDoctorLlm: () => ({ data: { provider: 'api', key_env: 'GEOMEMORY_LLM_API_KEY', key_configured: true, base_url: 'https://api.kilo.ai/api/gateway/v1', model_id: 'kilo-auto/free', context_window: 32768 }, isLoading: false }),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <DoctorPage />
    </QueryClientProvider>,
  )
}

describe('DoctorPage', () => {
  it('renders optional deps as installed', () => {
    renderPage()
    expect(screen.getByText('Pillow')).toBeInTheDocument()
    expect(screen.getByText('PyMuPDF')).toBeInTheDocument()
    expect(screen.getByText('python_docx')).toBeInTheDocument()
    expect(screen.getByText('sqlite-vec')).toBeInTheDocument()
  })

  it('has no [object Object] text and no GGUF path labels', () => {
    const { container } = renderPage()
    expect(container.textContent).not.toContain('[object Object]')
    expect(container.textContent).not.toMatch(/GGUF path/i)
  })

  it('renders test connection button for LLM', () => {
    renderPage()
    expect(screen.getByTestId('doctor-test-llm-btn')).toBeInTheDocument()
  })
})