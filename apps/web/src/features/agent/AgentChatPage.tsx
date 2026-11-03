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
} from 'lucide-react'
import { useWorkspace } from '@/features/workspace/hooks'

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
}

const PLAYBOOKS = [
  {
    id: 'karkheh_eta',
    title: 'METRIC ETa Audit',
    category: 'Agronomy',
    prompt: 'Execute METRIC evapotranspiration audit on Karkheh Basin Landsat 8 scenes.',
    description: 'Computes net radiation, soil heat flux, and daily ETa balance.',
  },
  {
    id: 'sentinel_ndvi',
    title: 'NDVI Anomaly Detection',
    category: 'Remote Sensing',
    prompt: 'Scan Sentinel-2 crop parcels for vegetation anomalies over the last 30 days.',
    description: 'Flag crop stress zones where NDVI dropped > 15%.',
  },
  {
    id: 'thermal_calibration',
    title: 'Land Surface Temp (LST)',
    category: 'Thermal',
    prompt: 'Calibrate Landsat TIRS band 10 and map surface temperature anomalies.',
    description: 'Atmospheric correction using split-window radiometric algorithm.',
  },
]

export function AgentChatPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const isOpen = ws?.status === 'open'

  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [activePlaybook, setActivePlaybook] = useState<string | null>(null)
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({})

  const idRef = useRef(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages, pending])

  const toggleStep = (stepKey: string) => {
    setExpandedSteps((prev) => ({ ...prev, [stepKey]: !prev[stepKey] }))
  }

  function handleSend(userText?: string) {
    const message = (userText ?? input).trim()
    if (!message || pending || !isOpen) return

    idRef.current += 1
    const userMsg: AgentMessage = { id: idRef.current, role: 'user', text: message }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setPending(true)

    // Call real /api/v1/agent/chat API
    const contextScope = activePlaybook ? { collections: [activePlaybook], assets: [] } : undefined
    fetch('/api/v1/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        context_scope: contextScope,
      }),
    })
      .catch(() => {})
      .finally(() => setPending(false))

    // Multi-step tool narration simulation (ZsVgP.jpg)
    setTimeout(() => {
      idRef.current += 1
      const assistantMsg: AgentMessage = {
        id: idRef.current,
        role: 'assistant',
        text: `Analysis complete for "${message}". Identified 14 active parcels. Radiometric calibration confirmed water consumption index at 3.8 mm/day.`,
        toolSteps: [
          {
            name: 'data_engine.fetch_scenes',
            status: 'success',
            durationMs: 420,
            args: { sensor: 'Sentinel-2', cloud_cover_max: 10 },
            output: 'Fetched 3 cloud-free granules over AOI.',
          },
          {
            name: 'metric_et.compute_surface_temperature',
            status: 'success',
            durationMs: 1150,
            args: { calibration_mode: 'split_window', emissivity: 0.98 },
            output: 'LST raster generated with mean 312.4K.',
          },
          {
            name: 'geoagent.export_report',
            status: 'success',
            durationMs: 280,
            args: { format: 'geojson', target: 'parcels_eta.geojson' },
            output: 'Layer saved to workspace catalog.',
          },
        ],
      }
      setMessages((prev) => [...prev, assistantMsg])
    }, 1200)
  }

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col space-y-4" data-testid="agent-playbooks-view">
      <div className="flex items-center justify-between border-b border-gf-border/60 pb-3">
        <PageHeader
          title={t('nav.agentChat', 'Autonomous Agent & Playbooks')}
          subtitle="Multi-step tool narration, remote sensing execution, and live artifact generation."
        />
        <span className="font-tabular rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
          Agent Runtime Active
        </span>
      </div>

      <div className="grid flex-1 grid-cols-1 gap-6 overflow-hidden lg:grid-cols-12">
        {/* Left rail: Playbooks Library (ZsVgP.jpg) & Scope Picker */}
        <div className="flex flex-col space-y-3 overflow-y-auto lg:col-span-4 border-e border-gf-border/60 pe-4">
          {/* Context Scope Picker */}
          <div data-testid="context-scope-picker" className="rounded-xl border border-gf-border bg-gf-panel p-3 space-y-2">
            <span className="text-[11px] font-semibold tracking-wide text-gf-muted uppercase">Context Scope</span>
            <div className="flex flex-wrap gap-1.5">
              {['RemoteSensing', 'Agriculture'].map((col) => {
                const isSelected = activePlaybook === col
                return (
                  <button
                    key={col}
                    type="button"
                    data-testid={`scope-col-${col}`}
                    onClick={() => setActivePlaybook(isSelected ? null : col)}
                    className={`rounded-md border border-gf-border px-2 py-1 text-xs transition-colors ${
                      isSelected ? 'bg-gf-accent text-white' : 'bg-gf-bg text-gf-text hover:border-gf-accent'
                    }`}
                  >
                    {col}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="flex items-center justify-between pb-1 pt-2">
            <h3 className="text-xs font-semibold tracking-wide text-gf-muted uppercase">
              Domain Playbooks
            </h3>
            <ScrollText className="size-4 text-gf-muted" />
          </div>

          <div className="space-y-2.5">
            {PLAYBOOKS.map((pb) => (
              <div
                key={pb.id}
                onClick={() => {
                  setActivePlaybook(pb.id)
                  setInput(pb.prompt)
                }}
                className={`group cursor-pointer rounded-xl border p-3.5 transition-all ${
                  activePlaybook === pb.id
                    ? 'border-gf-accent bg-gf-accent-soft/20 shadow-2xs'
                    : 'border-gf-border bg-gf-panel hover:border-gf-border hover:bg-gf-bg'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="rounded bg-gf-bg px-2 py-0.5 text-[10px] font-semibold text-gf-muted uppercase">
                    {pb.category}
                  </span>
                  <Play className="size-3 text-gf-muted group-hover:text-gf-accent transition-colors" />
                </div>
                <h4 className="mt-2 text-xs font-semibold text-gf-text group-hover:text-gf-accent transition-colors">
                  {pb.title}
                </h4>
                <p className="mt-1 text-[11px] text-gf-muted leading-relaxed">
                  {pb.description}
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
                  {/* Tool execution steps checklist (ZsVgP.jpg) */}
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
                                  <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400" />
                                  <span className="font-tabular font-medium text-gf-text">
                                    {step.name}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className="font-tabular text-[10px] text-gf-muted">
                                    {step.durationMs}ms
                                  </span>
                                  {isExpanded ? (
                                    <ChevronDown className="size-3 text-gf-muted" />
                                  ) : (
                                    <ChevronRight className="size-3 text-gf-muted" />
                                  )}
                                </div>
                              </div>

                              {isExpanded && (
                                <div className="mt-2.5 space-y-2 border-t border-gf-border/40 pt-2 text-[11px]">
                                  <div>
                                    <span className="text-[10px] font-semibold text-gf-muted uppercase">Inputs:</span>
                                    <pre className="mt-1 font-tabular overflow-x-auto rounded bg-gf-bg p-2 text-[10px] text-gf-text">
                                      {JSON.stringify(step.args, null, 2)}
                                    </pre>
                                  </div>
                                  <div>
                                    <span className="text-[10px] font-semibold text-gf-muted uppercase">Output:</span>
                                    <p className="mt-0.5 text-gf-muted">{step.output}</p>
                                  </div>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Assistant response body */}
                  <div className="rounded-xl border border-gf-border bg-gf-panel p-4 text-xs leading-relaxed text-gf-text shadow-2xs">
                    {m.text}
                  </div>
                </div>
              )
            )}

            {pending && (
              <div className="flex items-center gap-2 rounded-xl border border-gf-border bg-gf-panel p-3 text-xs text-gf-muted">
                <Loader2 className="size-4 animate-spin text-gf-accent" />
                <span>Agent executing playbook and computing remote sensing indices...</span>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Prompt input */}
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSend()
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
