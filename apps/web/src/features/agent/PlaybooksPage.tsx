import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery } from '@tanstack/react-query'
import { BookOpen, AlertTriangle, CheckCircle, Play, Loader2, X, AlertCircle } from 'lucide-react'
import { agentApi, type PlaybookSummary } from '@/api/agent'

export function PlaybooksPage() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['agent', 'playbooks'],
    queryFn: agentApi.listPlaybooks,
  })

  const [activePlaybook, setActivePlaybook] = useState<PlaybookSummary | null>(null)
  const [paramsJson, setParamsJson] = useState('{}')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [runError, setRunError] = useState<string | null>(null)

  const runMutation = useMutation({
    mutationFn: ({ name, params }: { name: string; params: Record<string, unknown> }) =>
      agentApi.runPlaybook(name, params),
    onSuccess: (res) => {
      setResult(res)
      setRunError(null)
    },
    onError: (err) => {
      setRunError(err instanceof Error ? err.message : String(err))
      setResult(null)
    },
  })

  function openRunner(pb: PlaybookSummary) {
    setActivePlaybook(pb)
    setResult(null)
    setRunError(null)
    setParamsJson(JSON.stringify(pb.params ?? {}, null, 2))
  }

  function handleRun() {
    if (!activePlaybook) return
    let parsedParams: Record<string, unknown> = {}
    try {
      parsedParams = JSON.parse(paramsJson)
    } catch {
      setRunError('Invalid JSON parameters')
      return
    }
    runMutation.mutate({ name: activePlaybook.name, params: parsedParams })
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('agent.playbooks.title', 'Playbooks')}</h1>

      {isLoading && <p className="text-sm text-gf-muted">{t('common.loading', 'Loading…')}</p>}
      {error && (
        <p className="text-sm text-gf-err" role="alert">
          {error instanceof Error ? error.message : String(error)}
        </p>
      )}

      {data?.playbooks.length === 0 && (
        <p className="text-sm text-gf-muted">
          {t('agent.playbooks.empty', 'No playbooks yet. Create one from the workspace playbooks/ folder.')}
        </p>
      )}

      <div className="space-y-3">
        {data?.playbooks.map((pb: PlaybookSummary) => (
          <div
            key={pb.name}
            className="rounded-lg border border-gf-border bg-gf-panel p-4"
          >
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BookOpen className="size-4 text-gf-accent" />
                <h3 className="text-sm font-semibold">{pb.name}</h3>
                <span className="text-xs text-gf-muted">v{pb.version}</span>
              </div>
              <div className="flex items-center gap-2">
                {pb.valid ? (
                  <span className="flex items-center gap-1 text-xs text-green-600">
                    <CheckCircle className="size-3.5" /> {t('agent.playbooks.valid', 'valid')}
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-xs text-red-600">
                    <AlertTriangle className="size-3.5" /> {t('agent.playbooks.invalid', 'invalid')}
                  </span>
                )}
                {pb.valid && (
                  <button
                    type="button"
                    onClick={() => openRunner(pb)}
                    className="flex items-center gap-1 rounded bg-gf-accent px-2 py-1 text-xs font-medium text-white transition-opacity hover:opacity-90"
                    data-testid={`run-playbook-${pb.name}`}
                  >
                    <Play className="size-3" /> {t('common.run', 'Run')}
                  </button>
                )}
              </div>
            </div>

            <p className="mb-2 text-xs text-gf-muted">
              {t('agent.playbooks.steps', 'Steps')}: {pb.steps.map((s) => s.tool).join(' → ')}
            </p>

            {pb.triggers.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-1">
                {pb.triggers.map((trigger, i) => (
                  <span
                    key={i}
                    className="rounded-full border border-gf-border px-2 py-0.5 text-[11px] text-gf-muted"
                  >
                    {trigger}
                  </span>
                ))}
              </div>
            )}

            {pb.problems.length > 0 && (
              <ul className="space-y-1 text-xs text-red-600">
                {pb.problems.map((p, i) => (
                  <li key={i}>• {p}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      {activePlaybook && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setActivePlaybook(null)}>
          <div
            className="w-full max-w-lg rounded-lg border border-gf-border bg-gf-panel p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
            data-testid="playbook-run-modal"
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BookOpen className="size-5 text-gf-accent" />
                <h2 className="font-semibold text-base">{activePlaybook.name}</h2>
              </div>
              <button
                type="button"
                onClick={() => setActivePlaybook(null)}
                className="rounded p-1 text-gf-muted hover:text-gf-text"
              >
                <X className="size-4" />
              </button>
            </div>

            <label className="block mb-3 text-xs font-medium text-gf-muted">
              {t('agent.playbooks.params', 'Parameters (JSON)')}
              <textarea
                value={paramsJson}
                onChange={(e) => setParamsJson(e.target.value)}
                rows={4}
                dir="ltr"
                className="mt-1 w-full rounded border border-gf-border bg-gf-bg p-2 font-mono text-xs outline-none focus:border-gf-accent"
              />
            </label>

            <div className="flex justify-end gap-2 mb-3">
              <button
                type="button"
                onClick={() => setActivePlaybook(null)}
                className="rounded border border-gf-border px-3 py-1.5 text-xs"
              >
                {t('common.cancel', 'Cancel')}
              </button>
              <button
                type="button"
                onClick={handleRun}
                disabled={runMutation.isPending}
                className="flex items-center gap-1.5 rounded bg-gf-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              >
                {runMutation.isPending && <Loader2 className="size-3 animate-spin" />}
                {runMutation.isPending ? t('common.running', 'Running…') : t('common.execute', 'Execute')}
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
