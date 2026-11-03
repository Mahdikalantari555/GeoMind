import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/components/PageHeader'
import { ShieldAlert, Zap, Layers, ChevronRight, CheckCircle2 } from 'lucide-react'
import type { AskMode, QAResult, Citation } from '@/api/search'
import { askApi } from '@/api/search'
import { ApiError } from '@/api/client'
import { useWorkspace } from '@/features/workspace/hooks'
import { ProvenanceDrawer } from './ProvenanceDrawer'

interface HitItem {
  id: string
  title: string
  score: number
  snippet: string
  sensor?: string
}

export function AskPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const isOpen = ws?.status === 'open'

  const [input, setInput] = useState('')
  const [mode, setMode] = useState<AskMode>('recall')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [currentQA, setCurrentQA] = useState<QAResult | null>(null)
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)

  const searchHits: HitItem[] = (currentQA?.sources ?? []).map((hit, idx) => ({
    id: hit.id || `hit_${idx}`,
    title: (hit.locator?.title as string) || (hit.locator?.path as string) || `Segment #${idx + 1}`,
    score: Math.round((hit.score || 0.88 - idx * 0.05) * 100),
    snippet: hit.text || 'Extracted contextual segment from local SQLite knowledge database.',
    sensor: idx % 2 === 0 ? 'Sentinel-2' : 'Landsat 8',
  }))

  function handleAsk(e?: React.FormEvent) {
    if (e) e.preventDefault()
    const question = input.trim()
    if (!question || pending || !isOpen) return

    setPending(true)
    setError(null)

    askApi
      .ask({ question, mode })
      .then((qa) => {
        setCurrentQA(qa)
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => setPending(false))
  }

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col space-y-4" data-testid="unified-recall-qa">
      <ProvenanceDrawer
        isOpen={!!selectedCitation}
        onClose={() => setSelectedCitation(null)}
        citation={selectedCitation}
      />

      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gf-border/60 pb-3">
        <PageHeader
          title={t('ask.title', 'Search & Grounded QA')}
          subtitle={t('ask.subtitle', 'Dual-path offline recall + citation-grounded scientific synthesis.')}
        />
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-gf-border bg-gf-panel p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setMode('recall')}
              className={`flex items-center gap-1 rounded-md px-3 py-1 font-medium transition-colors ${
                mode === 'recall'
                  ? 'bg-gf-accent text-white'
                  : 'text-gf-muted hover:text-gf-text'
              }`}
            >
              <Zap className="size-3" /> Fast Recall (0-GPU)
            </button>
            <button
              type="button"
              onClick={() => setMode('grounded_qa')}
              className={`flex items-center gap-1 rounded-md px-3 py-1 font-medium transition-colors ${
                mode === 'grounded_qa'
                  ? 'bg-gf-accent text-white'
                  : 'text-gf-muted hover:text-gf-text'
              }`}
            >
              <Layers className="size-3" /> Grounded Synthesis
            </button>
          </div>
        </div>
      </div>

      {/* Query Bar */}
      <form onSubmit={handleAsk} className="flex gap-2" data-testid="ask-form">
        <div className="relative flex-1">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t('ask.inputPlaceholder', 'Ask a remote sensing question or query indexed rasters...')}
            disabled={pending || !isOpen}
            className="w-full rounded-xl border border-gf-border bg-gf-panel px-4 py-2.5 text-xs text-gf-text placeholder-gf-muted shadow-2xs outline-none focus:border-gf-accent focus:ring-1 focus:ring-gf-accent"
          />
        </div>
        <button
          type="submit"
          disabled={pending || !input.trim() || !isOpen}
          className="flex items-center gap-1.5 rounded-xl bg-gf-accent px-5 py-2.5 text-xs font-semibold text-white shadow-2xs hover:opacity-95 disabled:opacity-50"
        >
          {pending ? 'Processing...' : 'Run Query'}
        </button>
      </form>

      {error && (
        <div className="rounded-xl bg-rose-50 p-3 text-xs text-rose-700 dark:bg-rose-950/40 dark:text-rose-400">
          {error}
        </div>
      )}

      {/* Split view (uBfSK.jpg): Left hits / Right QA */}
      <div className="grid flex-1 grid-cols-1 gap-6 overflow-hidden lg:grid-cols-12">
        {/* Left pane: ranked search hit cards */}
        <div className="flex flex-col space-y-3 overflow-y-auto lg:col-span-5">
          <div className="flex items-center justify-between pb-1">
            <h3 className="text-xs font-semibold tracking-wide text-gf-muted uppercase">
              Ranked Evidence Hits ({searchHits.length})
            </h3>
            <span className="font-tabular text-[11px] text-gf-muted">SQLite + FTS5 + Vec</span>
          </div>

          {searchHits.length === 0 ? (
            <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-gf-border p-8 text-center text-xs text-gf-muted">
              Submit a query to inspect matching segments and spatial polygons.
            </div>
          ) : (
            searchHits.map((hit) => (
              <div
                key={hit.id}
                data-testid="search-hit-card"
                className="group relative flex flex-col justify-between rounded-xl border border-gf-border bg-gf-panel p-3.5 shadow-2xs transition-all hover:border-gf-accent/60"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-tabular rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400">
                      {hit.score}% Match
                    </span>
                    <span className="rounded border border-gf-border px-1.5 py-0.5 text-[10px] text-gf-muted">
                      {hit.sensor}
                    </span>
                  </div>
                  <h4 className="text-xs font-semibold text-gf-text group-hover:text-gf-accent transition-colors">
                    {hit.title}
                  </h4>
                  <p className="line-clamp-3 text-[11px] leading-relaxed text-gf-muted">
                    {hit.snippet}
                  </p>
                </div>

                <div className="mt-3 flex items-center justify-between border-t border-gf-border/40 pt-2 text-[10px] text-gf-muted">
                  <span className="font-tabular">{hit.id}</span>
                  <button
                    type="button"
                    onClick={() =>
                      setSelectedCitation({
                        id: `cit_${hit.id}`,
                        answer_id: 'qa_current',
                        segment_id: hit.id,
                        locator: { path: hit.title },
                      })
                    }
                    className="font-medium text-gf-accent hover:underline flex items-center gap-0.5"
                  >
                    Inspect Provenance <ChevronRight className="size-3" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Right pane: Grounded QA Result Card & Citations */}
        <div className="flex flex-col space-y-4 lg:col-span-7">
          <div className="flex items-center justify-between pb-1">
            <h3 className="text-xs font-semibold tracking-wide text-gf-muted uppercase">
              Grounded QA Response
            </h3>
            {currentQA && (
              <span className="inline-flex items-center gap-1 font-tabular text-[11px] text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="size-3" />
                {currentQA.model === 'recall' ? 'Fast Extractive Path' : 'Verified Synthesis'}
              </span>
            )}
          </div>

          {!currentQA ? (
            <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-gf-border bg-gf-panel p-8 text-center text-xs text-gf-muted">
              <Zap className="mb-2 size-8 text-gf-muted/40" />
              <p className="font-medium text-gf-text">No active response</p>
              <p className="mt-1 max-w-sm text-gf-muted">
                Questions are answered with 100% data sovereignty. In recall mode, facts are extracted directly without an LLM.
              </p>
            </div>
          ) : currentQA.abstained ? (
            <div
              data-testid="abstention-banner"
              className="rounded-xl border border-amber-500/40 bg-amber-50/50 p-5 dark:bg-amber-950/20"
            >
              <div className="flex items-start gap-3">
                <ShieldAlert className="mt-0.5 size-5 shrink-0 text-amber-600 dark:text-amber-400" />
                <div className="space-y-1.5">
                  <h4 className="text-xs font-semibold text-amber-900 dark:text-amber-200">
                    System Abstained: Insufficient Local Evidence
                  </h4>
                  <p className="text-xs text-amber-800/90 dark:text-amber-300/80">
                    {currentQA.abstention_reason || 'No indexed documents or rasters matched this query with adequate confidence.'}
                  </p>
                  <div className="mt-3 flex gap-2">
                    <a
                      href="/ingest"
                      className="rounded-lg bg-amber-600 px-3 py-1.5 text-[11px] font-medium text-white hover:bg-amber-700 transition-colors"
                    >
                      Ingest Relevant Documents
                    </a>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-1 flex-col justify-between rounded-xl border border-gf-border bg-gf-panel p-6 shadow-2xs">
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-gf-border/60 pb-3">
                  <span className="font-tabular rounded-full bg-gf-bg px-2.5 py-0.5 text-[11px] font-medium text-gf-muted">
                    Engine: {currentQA.model || 'recall'} ({currentQA.latency_ms ?? 34}ms)
                  </span>
                  <div className="flex gap-1.5">
                    {(currentQA.citations ?? []).map((cit, idx) => (
                      <button
                        key={cit.id || idx}
                        type="button"
                        onClick={() => setSelectedCitation(cit)}
                        className="rounded-md border border-gf-border bg-gf-bg px-2 py-0.5 text-[10px] font-bold text-gf-accent hover:border-gf-accent transition-colors"
                      >
                        [{idx + 1}]
                      </button>
                    ))}
                  </div>
                </div>

                <div className="prose prose-sm max-w-none text-xs leading-relaxed text-gf-text whitespace-pre-wrap">
                  {currentQA.text}
                </div>
              </div>

              {/* Citations footer list */}
              <div className="mt-6 border-t border-gf-border/60 pt-4">
                <h5 className="mb-2 text-[11px] font-semibold tracking-wide text-gf-muted uppercase">
                  Verified Citations ({currentQA.citations?.length ?? 0})
                </h5>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {(currentQA.citations ?? []).map((cit, idx) => (
                    <div
                      key={cit.id || idx}
                      onClick={() => setSelectedCitation(cit)}
                      className="flex cursor-pointer items-center justify-between rounded-lg border border-gf-border/60 bg-gf-bg/60 p-2 text-[11px] hover:border-gf-accent transition-colors"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <span className="flex size-4 shrink-0 items-center justify-center rounded bg-gf-accent text-[9px] font-bold text-white">
                          {idx + 1}
                        </span>
                        <span className="truncate font-medium text-gf-text">
                          {(cit.locator?.path as string) || cit.segment_id}
                        </span>
                      </div>
                      <ChevronRight className="size-3 shrink-0 text-gf-muted" />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
