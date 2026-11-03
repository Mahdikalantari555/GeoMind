import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/components/PageHeader'
import {
  Send,
  Loader2,
  ScrollText,
  Play,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Terminal,
  Activity,
  AlertCircle,
} from 'lucide-react'
import { useWorkspace } from '@/features/workspace/hooks'
import { useCollections } from '@/features/knowledge/hooks'
import { useQuery } from '@tanstack/react-query'
import { agentApi, type PlaybookSummary } from '@/api/agent'

interface ToolStep {
  name: string
  status: 'pending' | 'running' | 'success' | 'error'
  durationMs?: number
  args?: Record<string, unknown>
  output?: string
}

interface AgentMessage {
  id: number
  role: 'user' | 'assistant'
  text: string
  toolSteps?: ToolStep[]
  isError?: boolean
}

export function AgentChatPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const { data: collectionsData } = useCollections()
  const collections = collectionsData ?? []
  const isOpen = ws?.status === 'open'

  const { data: playbooksData, isLoading: playbooksLoading } = useQuery({
    queryKey: ['agent', 'playbooks'],
    queryFn: agentApi.listPlaybooks,
    enabled: isOpen,
  })
  const playbooks = playbooksData?.playbooks ?? []

  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [selectedScope, setSelectedScope] = useState<string | null>(null)
  const [activePlaybook, setActivePlaybook] = useState<PlaybookSummary | null>(null)
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({})

  const idRef = useRef(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages, pending])

  const toggleStep = (stepKey: string) => {
    setExpandedSteps((prev) => ({ ...prev, [stepKey]: !prev[stepKey] }))
  }

  async function handleSend(userText?: string) {
    const message = (userText ?? input).trim()
    if (!message || pending || !isOpen) return

    idRef.current += 1
    const userMsg: AgentMessage = { id: idRef.current, role: 'user', text: message }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setPending(true)

    const contextScope = selectedScope ? { collections: [selectedScope], assets: [] } : undefined

    try {
      const response = await fetch('/api/v1/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          context_scope: contextScope,
        }),
      })

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`)
      }

      if (!response.body) {
        throw new Error('No response stream available')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let assistantText = ''
      const toolSteps: ToolStep[] = []
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim()
          if (!line.startsWith('data:')) continue

          const jsonStr = line.slice(5).trim()
          if (!jsonStr) continue

          try {
            const data = JSON.parse(jsonStr)
            if (data.tool) {
              const existing = toolSteps.find((s) => s.name === data.tool)
              if (existing) {
                existing.status = data.status === 'error' ? 'error' : 'success'
                if (data.status) existing.output = data.status
              } else {
                toolSteps.push({
                  name: data.tool,
                  status: 'running',
                  output: data.status,
                })
              }
            } else if (data.text) {
              assistantText += (assistantText ? '\n' : '') + data.text
            } else if (data.message && data.code) {
              assistantText += `\n[${data.code}]: ${data.message}`
            }
          } catch {
            // ignore non-JSON stream fragments
          }
        }
      }

      idRef.current += 1
      const assistantMsg: AgentMessage = {
        id: idRef.current,
        role: 'assistant',
        text: assistantText || 'Agent completed execution.',
        toolSteps: toolSteps.length > 0 ? toolSteps : undefined,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      idRef.current += 1
      const errorMsg: AgentMessage = {
        id: idRef.current,
        role: 'assistant',
        text: err instanceof Error ? err.message : String(err),
        isError: true,
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setPending(false)
    }
  }

  function handlePlaybookSelect(pb: PlaybookSummary) {
    setActivePlaybook(pb)
    const promptText = pb.triggers && pb.triggers.length > 0 ? pb.triggers[0] : `Run playbook ${pb.name}`
    setInput(promptText)
  }

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col space-y-4" data-testid="agent-playbooks-view">
      <div className="flex items-center justify-between border-b border-gf-border/60 pb-3">
        <PageHeader
          title={t('nav.agentChat', 'Autonomous Agent & Playbooks')}
          subtitle="Multi-step tool execution trace and verified workspace workflows."
        />
        <span className="font-tabular rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
          Agent Runtime Active
        </span>
      </div>

      <div className="grid flex-1 grid-cols-1 gap-6 overflow-hidden lg:grid-cols-12">
        {/* Left rail: Playbooks Library & Scope Picker */}
        <div className="flex flex-col space-y-3 overflow-y-auto lg:col-span-4 border-e border-gf-border/60 pe-4">
          {/* Context Scope Picker */}
          <div data-testid="context-scope-picker" className="rounded-xl border border-gf-border bg-gf-panel p-3 space-y-2">
            <span className="text-[11px] font-semibold tracking-wide text-gf-muted uppercase">Context Scope</span>
            <div className="flex flex-wrap gap-1.5">
              {collections.length === 0 ? (
                <span className="text-xs text-gf-muted">No collections available</span>
              ) : (
                collections.map((col) => {
                  const isSelected = selectedScope === col.name
                  return (
                    <button
                      key={col.id || col.name}
                      type="button"
                      data-testid={`scope-col-${col.name}`}
                      onClick={() => setSelectedScope(isSelected ? null : col.name)}
                      className={`rounded-md border border-gf-border px-2 py-1 text-xs transition-colors ${
                        isSelected ? 'bg-gf-accent text-white' : 'bg-gf-bg text-gf-text hover:border-gf-accent'
                      }`}
                    >
                      {col.name}
                    </button>
                  )
                })
              )}
            </div>
          </div>

          <div className="flex items-center justify-between pb-1 pt-2">
            <h3 className="text-xs font-semibold tracking-wide text-gf-muted uppercase">
              Domain Playbooks
            </h3>
            <ScrollText className="size-4 text-gf-muted" />
          </div>

          <div className="space-y-2.5">
            {playbooksLoading && (
              <p className="p-3 text-xs text-gf-muted">Loading workspace playbooks...</p>
            )}
            {!playbooksLoading && playbooks.length === 0 && (
              <div className="rounded-xl border border-dashed border-gf-border p-4 text-center text-xs text-gf-muted">
                No playbook definitions found in workspace <code className="font-tabular text-[10px]">playbooks/</code>.
              </div>
            )}
            {playbooks.map((pb) => (
              <div
                key={pb.name}
                onClick={() => handlePlaybookSelect(pb)}
                className={`group cursor-pointer rounded-xl border p-3.5 transition-all ${
                  activePlaybook?.name === pb.name
                    ? 'border-gf-accent bg-gf-accent-soft/20 shadow-2xs'
                    : 'border-gf-border bg-gf-panel hover:border-gf-border hover:bg-gf-bg'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-tabular rounded bg-gf-bg border border-gf-border px-2 py-0.5 text-[10px] font-semibold text-gf-muted uppercase">
                    v{pb.version}
                  </span>
                  <Play className="size-3 text-gf-muted group-hover:text-gf-accent transition-colors" />
                </div>
                <h4 className="mt-2 text-xs font-semibold text-gf-text group-hover:text-gf-accent transition-colors">
                  {pb.name}
                </h4>
                <p className="mt-1 text-[11px] text-gf-muted leading-relaxed font-tabular">
                  {pb.steps.map((s) => s.tool).join(' → ')}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Center/Right: Agent Chat & Tool Execution Log */}
        <div className="flex flex-col space-y-3 lg:col-span-8">
          <div
            className="flex-1 space-y-4 overflow-y-auto rounded-xl border border-gf-border bg-gf-panel p-5 shadow-2xs"
            data-testid="agent-chat-log"
          >
            {messages.length === 0 && !pending && (
              <div className="flex h-full flex-col items-center justify-center text-center p-8 text-xs text-gf-muted">
                <Terminal className="mb-2 size-8 text-gf-muted/40" />
                <p className="font-semibold text-gf-text">Select a Playbook or type an instruction</p>
                <p className="mt-1 max-w-md text-gf-muted">
                  The agent plans multi-step pipelines, executes geospatial tools with real-time feedback, and emits verifiable artifacts.
                </p>
              </div>
            )}

            {messages.map((m) =>
              m.role === 'user' ? (
                <div key={m.id} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-ee-sm bg-gf-accent px-4 py-2.5 text-xs text-white">
                    {m.text}
                  </div>
                </div>
              ) : (
                <div key={m.id} className="space-y-3">
                  {/* Tool execution steps trace */}
                  {m.toolSteps && m.toolSteps.length > 0 && (
                    <div className="rounded-xl border border-gf-border/80 bg-gf-bg/60 p-3.5 space-y-2">
                      <div className="flex items-center justify-between border-b border-gf-border/40 pb-2">
                        <span className="text-[11px] font-semibold tracking-wide text-gf-muted uppercase flex items-center gap-1.5">
                          <Activity className="size-3.5 text-gf-accent" /> Tool Execution Trace
                        </span>
                        <span className="font-tabular text-[10px] text-gf-muted">
                          {m.toolSteps.length} steps resolved
                        </span>
                      </div>

                      <div className="space-y-1.5">
                        {m.toolSteps.map((step, sIdx) => {
                          const stepKey = `${m.id}_${sIdx}`
                          const isExpanded = !!expandedSteps[stepKey]
                          return (
                            <div
                              key={stepKey}
                              className="rounded-lg border border-gf-border/60 bg-gf-panel p-2.5 text-xs"
                            >
                              <div
                                onClick={() => toggleStep(stepKey)}
                                className="flex cursor-pointer items-center justify-between"
                              >
                                <div className="flex items-center gap-2">
                                  {step.status === 'error' ? (
                                    <AlertCircle className="size-3.5 text-rose-600" />
                                  ) : (
                                    <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400" />
                                  )}
                                  <span className="font-tabular font-medium text-gf-text">
                                    {step.name}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2">
                                  {step.durationMs && (
                                    <span className="font-tabular text-[10px] text-gf-muted">
                                      {step.durationMs}ms
                                    </span>
                                  )}
                                  {isExpanded ? (
                                    <ChevronDown className="size-3 text-gf-muted" />
                                  ) : (
                                    <ChevronRight className="size-3 text-gf-muted" />
                                  )}
                                </div>
                              </div>

                              {isExpanded && (
                                <div className="mt-2.5 space-y-2 border-t border-gf-border/40 pt-2 text-[11px]">
                                  {step.args && (
                                    <div>
                                      <span className="text-[10px] font-semibold text-gf-muted uppercase">Inputs:</span>
                                      <pre className="mt-1 font-tabular overflow-x-auto rounded bg-gf-bg p-2 text-[10px] text-gf-text">
                                        {JSON.stringify(step.args, null, 2)}
                                      </pre>
                                    </div>
                                  )}
                                  {step.output && (
                                    <div>
                                      <span className="text-[10px] font-semibold text-gf-muted uppercase">Output:</span>
                                      <p className="mt-0.5 text-gf-muted">{step.output}</p>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Assistant response body */}
                  <div className={`rounded-xl border p-4 text-xs leading-relaxed shadow-2xs ${
                    m.isError
                      ? 'border-rose-500/40 bg-rose-50/50 text-rose-800 dark:bg-rose-950/20 dark:text-rose-300'
                      : 'border-gf-border bg-gf-panel text-gf-text'
                  }`}>
                    {m.text}
                  </div>
                </div>
              )
            )}

            {pending && (
              <div className="flex items-center gap-2 rounded-xl border border-gf-border bg-gf-panel p-3 text-xs text-gf-muted">
                <Loader2 className="size-4 animate-spin text-gf-accent" />
                <span>Agent executing tools against active workspace...</span>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Prompt input */}
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void handleSend()
            }}
            className="flex gap-2"
          >
            <input
              type="text"
              data-testid="agent-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Give the agent a task or select a playbook above..."
              disabled={pending || !isOpen}
              className="flex-1 rounded-xl border border-gf-border bg-gf-panel px-4 py-2.5 text-xs text-gf-text placeholder-gf-muted shadow-2xs outline-none focus:border-gf-accent focus:ring-1 focus:ring-gf-accent"
            />
            <button
              type="submit"
              data-testid="agent-send"
              disabled={pending || !input.trim() || !isOpen}
              className="flex items-center gap-1.5 rounded-xl bg-gf-accent px-5 py-2.5 text-xs font-semibold text-white shadow-2xs hover:opacity-95 disabled:opacity-50"
            >
              <Send className="size-3.5" /> Run
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
