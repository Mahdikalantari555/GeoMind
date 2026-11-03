import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/EmptyState'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Wrench, Clock, Database, Play, Loader2, X, AlertCircle } from 'lucide-react'
import { agentApi, type AgentTool } from '@/api/agent'

export function ToolsPage() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['agent', 'tools'],
    queryFn: agentApi.listTools,
  })

  const [activeTool, setActiveTool] = useState<AgentTool | null>(null)
  const [paramsJson, setParamsJson] = useState('{}')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [runError, setRunError] = useState<string | null>(null)

  const callMutation = useMutation({
    mutationFn: ({ name, args }: { name: string; args: Record<string, unknown> }) =>
      agentApi.callTool(name, args),
    onSuccess: (res) => {
      setResult(res)
      setRunError(null)
    },
    onError: (err) => {
      setRunError(err instanceof Error ? err.message : String(err))
      setResult(null)
    },
  })

  function openRunner(tool: AgentTool) {
    setActiveTool(tool)
    setResult(null)
    setRunError(null)
    // Build default params template
    const def: Record<string, unknown> = {}
    if (tool.params && typeof tool.params === 'object') {
      const p = (tool.params as Record<string, unknown>).properties as Record<string, unknown> | undefined
      if (p) {
        for (const [k, v] of Object.entries(p)) {
          def[k] = (v as Record<string, unknown>).default ?? ''
        }
      }
    }
    setParamsJson(JSON.stringify(def, null, 2))
  }

  function handleRun() {
    if (!activeTool) return
    let parsedArgs: Record<string, unknown> = {}
    try {
      parsedArgs = JSON.parse(paramsJson)
    } catch {
      setRunError('Invalid JSON parameters')
      return
    }
    callMutation.mutate({ name: activeTool.name, args: parsedArgs })
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <PageHeader title={t('agent.tools.title', 'Agent Tools')} />

      {isLoading && <p className="text-sm text-gf-muted">{t('common.loading', 'Loading…')}</p>}
      {error && (
        <p className="text-sm text-gf-err" role="alert">
          {error instanceof Error ? error.message : String(error)}
        </p>
      )}

      {data?.tools?.length === 0 && (
        <EmptyState title={t('agent.tools.empty', 'No tools available')} description={t('agent.tools.emptyHint', 'Tools appear when the gateway exposes them.')} />
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {data?.tools.map((tool: AgentTool) => (
          <div
            key={tool.name}
            className="flex flex-col justify-between rounded-lg border border-gf-border bg-gf-panel p-4"
          >
            <div>
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Wrench className="size-4 text-gf-accent" />
                  <h3 className="text-sm font-semibold">{tool.name}</h3>
                </div>
                <button
                  type="button"
                  onClick={() => openRunner(tool)}
                  className="flex items-center gap-1 rounded bg-gf-accent px-2 py-1 text-xs font-medium text-white transition-opacity hover:opacity-90"
                  data-testid={`invoke-tool-${tool.name}`}
                >
                  <Play className="size-3" /> {t('common.run', 'Run')}
                </button>
              </div>
              <p className="mb-3 text-xs text-gf-muted">{tool.description}</p>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-gf-muted">
              <span className="flex items-center gap-1">
                <Clock className="size-3" /> {tool.timeout_s}s
              </span>
              {tool.cacheable && (
                <span className="flex items-center gap-1">
                  <Database className="size-3" /> {t('agent.tools.cacheable', 'cacheable')}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {activeTool && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setActiveTool(null)}>
          <div
            className="w-full max-w-lg rounded-lg border border-gf-border bg-gf-panel p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
            data-testid="tool-run-modal"
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Wrench className="size-5 text-gf-accent" />
                <h2 className="font-semibold text-base">{activeTool.name}</h2>
              </div>
              <button
                type="button"
                onClick={() => setActiveTool(null)}
                className="rounded p-1 text-gf-muted hover:text-gf-text"
              >
                <X className="size-4" />
              </button>
            </div>
            <p className="mb-3 text-xs text-gf-muted">{activeTool.description}</p>

            <label className="block mb-3 text-xs font-medium text-gf-muted">
              {t('agent.tools.params', 'Parameters (JSON)')}
              <textarea
                value={paramsJson}
                onChange={(e) => setParamsJson(e.target.value)}
                rows={5}
                dir="ltr"
                className="mt-1 w-full rounded border border-gf-border bg-gf-bg p-2 font-mono text-xs outline-none focus:border-gf-accent"
              />
            </label>

            <div className="flex justify-end gap-2 mb-3">
              <button
                type="button"
                onClick={() => setActiveTool(null)}
                className="rounded border border-gf-border px-3 py-1.5 text-xs"
              >
                {t('common.cancel', 'Cancel')}
              </button>
              <button
                type="button"
                onClick={handleRun}
                disabled={callMutation.isPending}
                className="flex items-center gap-1.5 rounded bg-gf-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              >
                {callMutation.isPending && <Loader2 className="size-3 animate-spin" />}
                {callMutation.isPending ? t('common.running', 'Running…') : t('common.execute', 'Execute')}
              </button>
            </div>

            {runError && (
              <div className="mb-3 flex items-start gap-2 rounded border border-gf-err/50 bg-gf-err/10 p-2.5 text-xs text-gf-err" role="alert">
                <AlertCircle className="size-4 shrink-0 mt-0.5" />
                <span>{runError}</span>
              </div>
            )}

            {result && (
              <div className="space-y-1">
                <h4 className="text-xs font-medium text-gf-muted">{t('common.result', 'Result')}</h4>
                <pre dir="ltr" className="max-h-48 overflow-auto rounded bg-gf-bg p-2.5 font-mono text-start text-xs leading-relaxed">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
