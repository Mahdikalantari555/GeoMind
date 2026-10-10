import '@/i18n'
import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AgentChatPage } from './AgentChatPage'

vi.mock('@/features/workspace/hooks', () => ({
  useWorkspace: () => ({ data: { status: 'open', name: 'Test WS' } }),
}))

vi.mock('@/features/knowledge/hooks', () => ({
  useCollections: () => ({
    data: [
      { id: 'c1', name: 'RemoteSensing' },
      { id: 'c2', name: 'Agriculture' },
    ],
  }),
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AgentChatPage />
    </QueryClientProvider>,
  )
}

describe('AgentChatPage', () => {
  it('renders chat interface and context scope picker', () => {
    renderPage()
    expect(screen.getByTestId('agent-chat-log')).toBeDefined()
    expect(screen.getByTestId('context-scope-picker')).toBeDefined()
    expect(screen.getByText('RemoteSensing')).toBeDefined()
    expect(screen.getByText('Agriculture')).toBeDefined()
  })

  it('toggles collection scope on chip click', () => {
    renderPage()
    const rsChip = screen.getByTestId('scope-col-RemoteSensing')
    fireEvent.click(rsChip)
    expect(rsChip.className).toContain('bg-gf-accent')
  })

  it('sends message with context scope', () => {
    const fetchMock = vi.fn().mockReturnValue(
      Promise.resolve({
        ok: true,
        body: {
          getReader: () => ({
            read: vi
              .fn()
              .mockResolvedValueOnce({
                done: false,
                value: new TextEncoder().encode(
                  'event: message\ndata: {"text":"hello world","final":true}\n\nevent: done\ndata: {}\n\n'
                ),
              })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          }),
        },
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()
    const rsChip = screen.getByTestId('scope-col-RemoteSensing')
    act(() => {
      fireEvent.click(rsChip)
    })

    const input = screen.getByTestId('agent-input')
    act(() => {
      fireEvent.change(input, { target: { value: 'Analyze crop stress' } })
    })

    const sendBtn = screen.getByTestId('agent-send')
    act(() => {
      fireEvent.click(sendBtn)
    })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/agent/chat',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          message: 'Analyze crop stress',
          context_scope: { collections: ['RemoteSensing'], assets: [] },
        }),
      })
    )
  })
})
