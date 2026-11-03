import { useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/components/PageHeader'
import { useQueryClient } from '@tanstack/react-query'
import { Upload, FileWarning, CheckCircle2, Loader2, Copy, AlertCircle } from 'lucide-react'
import { useCollections, useIngest, useJobPolling } from './hooks'
import { useWorkspace } from '@/features/workspace/hooks'
import { ApiError } from '@/api/client'
import { ingestApi, jobsApi } from '@/api/knowledge'
import { cn } from '@/lib/utils'

const ACCEPT = '.txt,.md,.markdown,.csv,.pdf,.py,.js,.ipynb,.geojson,.gpkg,.tif,.tiff'

type IngestState =
  | { phase: 'idle' }
  | { phase: 'uploading'; filename: string }
  | { phase: 'error'; filename: string; message: string; detail?: unknown; code?: string }

interface BatchItem {
  id: string
  name: string
  status: 'uploading' | 'queued' | 'running' | 'completed' | 'failed' | 'error' | 'skipped'
  progress: number
  message?: string
  skipped?: boolean
  segmentCount?: number
}

export function IngestPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const { data: collections } = useCollections()
  const { data: ws } = useWorkspace()
  const isOpen = ws?.status === 'open'
  const ingest = useIngest()
  const [collectionId, setCollectionId] = useState('')
  const [indexAfter, setIndexAfter] = useState(true)
  const [dragOver, setDragOver] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [state, setState] = useState<IngestState>({ phase: 'idle' })
  const [batch, setBatch] = useState<BatchItem[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  const effectiveCollectionId = collectionId || collections?.[0]?.id || ''

  const { data: job, refetch: refetchJob } = useJobPolling(jobId)

  const outcome = useMemo(() => {
    if (!job || job.status === 'pending' || job.status === 'running') return null
    if (job.status === 'failed' || job.status === 'error') {
      return { kind: 'error' as const, message: job.error ?? t('ingest.failed') }
    }
    const r = (job.result ?? {}) as Record<string, unknown>
    return {
      kind: 'done' as const,
      skipped: r.skipped === true,
      segmentCount: typeof r.segment_count === 'number' ? r.segment_count : undefined,
      reason: typeof r.reason === 'string' ? r.reason : undefined,
    }
  }, [job, t])

  const isSubmitting = ingest.isPending || job?.status === 'pending' || job?.status === 'running'

  function formatError(e: unknown): { msg: string; detail?: unknown; code?: string } {
    const isApi = e instanceof ApiError
    const detail = isApi ? e.detail : undefined
    const code = isApi ? e.code : undefined
    let msg = isApi ? e.message : String(e)
    if (code === 'unsupported_format' && detail && typeof detail === 'object' && 'accepted' in (detail as Record<string, unknown>)) {
      const acc = (detail as Record<string, unknown>).accepted
      msg += acc ? ` — accepted: ${Array.isArray(acc) ? acc.join(', ') : String(acc)}` : ''
    }
    if (code === 'payload_too_large' && detail && typeof detail === 'object') {
      const d = detail as Record<string, unknown>
      msg += ` — size ${d.size_bytes ?? '?'} / limit ${d.limit_bytes ?? '?'}`
    }
    return { msg, detail, code }
  }

  function startSingleUpload(file: File) {
    setBatch([])
    setState({ phase: 'uploading', filename: file.name })
    ingest.mutate(
      { file, collectionId: effectiveCollectionId, indexAfter },
      {
        onSuccess: (resp) => setJobId(resp.job_id),
        onError: (e) => {
          const { msg, detail, code } = formatError(e)
          setState({ phase: 'error', filename: file.name, message: msg, detail, code })
        },
      }
    )
  }

  async function startBatchUpload(files: File[]) {
    setState({ phase: 'idle' })
    setJobId(null)
    const initialItems: BatchItem[] = files.map((f, i) => ({
      id: `${f.name}-${i}-${Date.now()}`,
      name: f.name,
      status: 'uploading',
      progress: 0,
    }))
    setBatch(initialItems)

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const itemId = initialItems[i].id

      try {
        const resp = await ingestApi.file(file, effectiveCollectionId, indexAfter)
        setBatch((prev) =>
          prev.map((it) => (it.id === itemId ? { ...it, status: 'queued', progress: 0.1 } : it))
        )

        // Poll job
        let terminal = false
        while (!terminal) {
          await new Promise((res) => setTimeout(res, 500))
          try {
            const j = await jobsApi.get(resp.job_id)
            if (j.status === 'completed') {
              terminal = true
              const r = (j.result ?? {}) as Record<string, unknown>
              setBatch((prev) =>
                prev.map((it) =>
                  it.id === itemId
                    ? {
                        ...it,
                        status: r.skipped ? 'skipped' : 'completed',
                        progress: 1,
                        skipped: r.skipped === true,
                        segmentCount: typeof r.segment_count === 'number' ? r.segment_count : undefined,
                      }
                    : it
                )
              )
            } else if (j.status === 'failed' || j.status === 'error') {
              terminal = true
              setBatch((prev) =>
                prev.map((it) =>
                  it.id === itemId
                    ? { ...it, status: 'failed', progress: 1, message: j.error ?? t('ingest.failed') }
                    : it
                )
              )
            } else {
              setBatch((prev) =>
                prev.map((it) =>
                  it.id === itemId ? { ...it, status: 'running', progress: j.progress || 0.5 } : it
                )
              )
            }
          } catch (pollErr) {
            terminal = true
            setBatch((prev) =>
              prev.map((it) =>
                it.id === itemId
                  ? { ...it, status: 'error', message: String(pollErr) }
                  : it
              )
            )
          }
        }
      } catch (err) {
        const { msg } = formatError(err)
        setBatch((prev) =>
          prev.map((it) =>
            it.id === itemId ? { ...it, status: 'error', message: msg } : it
          )
        )
      }
    }

    void qc.invalidateQueries({ queryKey: ['assets'] })
    void qc.invalidateQueries({ queryKey: ['stats'] })
  }

  function handleFiles(files: FileList | File[]) {
    const list = Array.from(files)
    if (list.length === 0) return
    if (!isOpen) {
      setState({ phase: 'error', filename: list[0].name, message: 'No workspace open — open a workspace first.' })
      return
    }
    if (!effectiveCollectionId) {
      setState({ phase: 'error', filename: list[0].name, message: t('ingest.noCollection') })
      return
    }
    if (list.length === 1) {
      startSingleUpload(list[0])
    } else {
      void startBatchUpload(list)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageHeader title={t('ingest.title')} />

      {!isOpen && (
        <div className="flex items-center gap-2 rounded-lg border border-gf-warn/50 bg-gf-warn/10 p-3 text-sm" role="alert">
          <AlertCircle className="size-4 text-gf-warn" />
          <span>{t('search.closedWorkspace')}</span>
        </div>
      )}

      <div className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-gf-muted">{t('ingest.collection')}</span>
            <select
              value={effectiveCollectionId}
              onChange={(e) => setCollectionId(e.target.value)}
              disabled={!isOpen}
              className="min-w-40 rounded-md border border-gf-border bg-gf-bg px-2 py-1.5 text-sm disabled:opacity-50"
              data-testid="ingest-collection"
            >
              {(collections ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={indexAfter} onChange={(e) => setIndexAfter(e.target.checked)} disabled={!isOpen} />
            {t('ingest.indexAfter')}
          </label>
        </div>
        <p className="text-xs text-gf-muted">{t('ingest.formats')}</p>
        {!effectiveCollectionId && isOpen && (
          <p className="text-xs text-gf-err">{t('ingest.selectCollection')}</p>
        )}
      </div>

      <div
        role="button"
        tabIndex={0}
        onClick={() => isOpen && inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && isOpen && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          if (isOpen) setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (!isOpen) return
          if (e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files)
          }
        }}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-10 transition-colors',
          !isOpen && 'cursor-not-allowed opacity-50',
          dragOver ? 'border-gf-accent bg-gf-accent-soft/40' : 'border-gf-border bg-gf-panel'
        )}
        data-testid="ingest-dropzone"
      >
        <Upload className="size-8 text-gf-accent" />
        <p className="text-sm font-medium">{t('ingest.dropTitle')}</p>
        <p className="text-xs text-gf-muted">{t('ingest.dropHint')}</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          className="hidden"
          disabled={!isOpen}
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              handleFiles(e.target.files)
            }
            e.target.value = ''
          }}
        />
      </div>

      {batch.length > 0 && (
        <div className="space-y-2 rounded-lg border border-gf-border bg-gf-panel p-4 text-sm" data-testid="ingest-batch">
          <div className="flex items-center justify-between">
            <h2 className="font-medium text-sm">Batch Ingestion ({batch.filter((b) => b.status === 'completed' || b.status === 'skipped').length} / {batch.length})</h2>
            <button
              type="button"
              onClick={() => setBatch([])}
              className="rounded border border-gf-border px-2 py-0.5 text-xs text-gf-muted hover:text-gf-text"
            >
              {t('ingest.dismiss')}
            </button>
          </div>
          <div className="divide-y divide-gf-border/50">
            {batch.map((it) => (
              <div key={it.id} className="flex items-center justify-between py-2 text-xs">
                <span className="font-medium truncate max-w-xs">{it.name}</span>
                <div className="flex items-center gap-2">
                  {it.status === 'uploading' && <span className="flex items-center gap-1 text-gf-muted"><Loader2 className="size-3 animate-spin text-gf-accent" /> Uploading</span>}
                  {it.status === 'queued' && <span className="flex items-center gap-1 text-gf-muted"><Loader2 className="size-3 animate-spin text-gf-accent" /> Queued</span>}
                  {it.status === 'running' && <span className="flex items-center gap-1 text-gf-accent"><Loader2 className="size-3 animate-spin text-gf-accent" /> {Math.round(it.progress * 100)}%</span>}
                  {it.status === 'completed' && <span className="flex items-center gap-1 text-gf-ok"><CheckCircle2 className="size-3" /> {it.segmentCount ?? 0} segs</span>}
                  {it.status === 'skipped' && <span className="flex items-center gap-1 text-gf-warn"><Copy className="size-3" /> Skipped</span>}
                  {(it.status === 'failed' || it.status === 'error') && <span className="flex items-center gap-1 text-gf-err"><FileWarning className="size-3" /> {it.message ?? 'Failed'}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {isSubmitting && (
        <div className="flex items-center gap-2 rounded-lg border border-gf-border bg-gf-panel p-4 text-sm">
          <Loader2 className="size-4 animate-spin text-gf-accent" />
          {state.phase === 'uploading' ? t('ingest.processing', { name: state.filename }) : `Job ${job?.status ?? 'queued'}…`}
          {job && <span className="ms-auto font-mono text-xs">{job.status} · {Math.round(job.progress * 100)}%</span>}
        </div>
      )}

      {state.phase === 'error' && !outcome && (
        <div className="flex items-start gap-2 rounded-lg border border-gf-err/50 bg-gf-err/10 p-4 text-sm" role="alert">
          <FileWarning className="mt-0.5 size-4 shrink-0 text-gf-err" />
          <div className="flex-1">
            <p className="font-medium text-gf-err">{state.filename} — {state.code ?? 'error'}</p>
            <p className="text-xs">{state.message}</p>
            {state.code === 'unsupported_format' && Boolean(state.detail) && (
              <p className="mt-1 text-xs text-gf-muted">Accepted: {String(((state.detail as unknown as Record<string, unknown>).accepted as unknown as string[] | undefined)?.join(', ') ?? '')}</p>
            )}
          </div>
          <button type="button" onClick={() => setState({ phase: 'idle' })} className="rounded border border-gf-border px-2 py-1 text-xs">{t('ingest.dismiss')}</button>
        </div>
      )}

      {outcome?.kind === 'done' && (
        <div
          className={cn(
            'flex items-start gap-2 rounded-lg border p-4 text-sm',
            outcome.skipped ? 'border-gf-warn/50 bg-gf-warn/10' : 'border-gf-ok/50 bg-gf-ok/10'
          )}
          data-testid="ingest-result"
        >
          {outcome.skipped ? <Copy className="mt-0.5 size-4 shrink-0 text-gf-warn" /> : <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-gf-ok" />}
          <div>
            {outcome.skipped ? (
              <>
                <p className="font-medium text-gf-warn">{t('ingest.duplicateTitle', { name: state.phase === 'idle' ? '' : (state as { filename?: string }).filename ?? '' })}</p>
                <p className="text-xs text-gf-muted">{t('ingest.duplicateBody')}{outcome.reason ? ` (${outcome.reason})` : ''}</p>
              </>
            ) : (
              <p className="font-medium text-gf-ok">{t('ingest.successTitle', { name: state.phase === 'idle' ? '' : (state as { filename?: string }).filename ?? '', count: outcome.segmentCount ?? 0 })}</p>
            )}
          </div>
        </div>
      )}

      {outcome?.kind === 'error' && (
        <div className="flex items-start gap-2 rounded-lg border border-gf-err/50 bg-gf-err/10 p-4 text-sm" role="alert">
          <FileWarning className="mt-0.5 size-4 shrink-0 text-gf-err" />
          <div className="flex-1">
            <p className="font-medium text-gf-err">{state.phase === 'idle' ? '' : (state as { filename?: string }).filename ?? ''}</p>
            <p className="text-xs">{outcome.message}</p>
          </div>
          <button type="button" onClick={() => refetchJob()} className="rounded border border-gf-border px-2 py-1 text-xs">{t('ingest.retry')}</button>
        </div>
      )}
    </div>
  )
}
