import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Download, Save, Loader2, CheckCircle2, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ApiError } from '@/api/client'
import type { WorkspaceSettings } from '@/api/workspace'
import { useUpdateSettings, useVisionDownloadModel } from './modelHooks'
import { useWorkspace } from './hooks'
import { useJobPolling } from '@/features/knowledge/hooks'
import { useModels, useDownloadModel, formatBytes } from './modelHooks'
import { environmentApi } from '@/api/environment'

const DEFAULT_KEY_ENV = 'GEOMEMORY_LLM_API_KEY'
const EMBEDDING_BACKENDS = ['hashing', 'sentence-transformers', 'onnx', 'llama-cpp'] as const

export function SettingsPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const update = useUpdateSettings()
  const settings = ws?.settings ?? null

  const [form, setForm] = useState<WorkspaceSettings | null>(() => settings)
  const [prevSettings, setPrevSettings] = useState(settings)
  const [apiKey, setApiKey] = useState('')
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hfEndpoint, setHfEndpoint] = useState('')
  const [embeddingRoot, setEmbeddingRoot] = useState('')

  if (settings !== prevSettings) {
    setPrevSettings(settings)
    setForm(settings)
    setHfEndpoint('')
    setEmbeddingRoot('')
  }

  if (!settings || !form) {
    return (
      <div className="mx-auto max-w-3xl" data-testid="settings-page">
        <h1 className="text-2xl font-semibold">{t('settings.title')}</h1>
        <p className="mt-4 text-sm text-gf-muted">{t('closedWorkspace')}</p>
      </div>
    )
  }

  function set<K extends keyof WorkspaceSettings>(key: K, value: WorkspaceSettings[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev))
  }

  function submit() {
    if (!form) return
    setError(null)
    setSaved(false)
    const body: Record<string, unknown> = {
      name: form.name,
      language: form.language,
      offline: form.offline,
      model_path: form.model_path,
      embedding_path: form.embedding_path,
      vision_path: form.vision_path,
      batch_size: form.batch_size,
      thread_count: form.thread_count,
      llm_provider: form.llm_provider,
      llm_api_base_url: form.llm_api_base_url,
      llm_api_key_env: form.llm_api_key_env || DEFAULT_KEY_ENV,
      llm_model_id: form.llm_model_id,
      llm_context_window: form.llm_context_window,
      embedding_backend: form.embedding_backend,
      st_model_name: form.st_model_name,
      onnx_model_name: form.onnx_model_name,
      vector_backend: form.vector_backend,
      pdf_parser: form.pdf_parser,
    }
    if (apiKey.trim()) {
      ;(body as Record<string, unknown>).llm_api_key = apiKey.trim()
    }
    const env: Record<string, string> = {}
    if (hfEndpoint.trim()) env.HF_ENDPOINT = hfEndpoint.trim()
    if (embeddingRoot.trim()) env.GEOMEMORY_EMBEDDING_ROOT = embeddingRoot.trim()
    update.mutate(body, {
      onSuccess: async () => {
        setSaved(true)
        if (Object.keys(env).length > 0) {
          try {
            await environmentApi.setOverrides(env)
          } catch {
            /* best effort */
          }
        }
      },
      onError: (e) => setError(e instanceof ApiError ? e.message : String(e)),
    })
  }

  const inputCls =
    'w-full rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm outline-none focus:border-gf-accent'

  return (
    <div className="mx-auto max-w-3xl space-y-6" data-testid="settings-page">
      <h1 className="text-2xl font-semibold">{t('settings.title')}</h1>

      {/* ── General ─────────────────────────────────────────────── */}
      <section className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
        <h2 className="text-sm font-medium text-gf-muted">{t('settings.general')}</h2>
        <label className="block text-sm">
          {t('settings.name')}
          <input className={inputCls} value={form.name} onChange={(e) => set('name', e.target.value)} />
        </label>
        <label className="block text-sm">
          {t('settings.language')}
          <input
            className={inputCls}
            value={form.language ?? ''}
            onChange={(e) => set('language', e.target.value || null)}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.offline}
            onChange={(e) => set('offline', e.target.checked)}
          />
          {t('settings.offline')}
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            {t('settings.batchSize')}
            <input
              type="number"
              className={inputCls}
              value={form.batch_size}
              onChange={(e) => set('batch_size', Number(e.target.value))}
            />
          </label>
          <label className="block text-sm">
            {t('settings.threadCount')}
            <input
              type="number"
              className={inputCls}
              value={form.thread_count}
              onChange={(e) => set('thread_count', Number(e.target.value))}
            />
          </label>
        </div>
      </section>

      {/* ── Embedding Models ──────────────────────────────────────────── */}
      <EmbeddingModelsSection
        form={form}
        set={set}
        inputCls={inputCls}
        offline={form.offline}
      />

      <VisionModelsSection form={form} offline={form.offline} />

      {/* ── LLM Compute ─────────────────────────────────────────── */}
      <section className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
        <h2 className="text-sm font-medium text-gf-muted">{t('settings.llm')}</h2>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            {t('settings.llmProvider')}
            <input
              className={inputCls}
              value={form.llm_provider ?? ''}
              onChange={(e) => set('llm_provider', e.target.value || null)}
            />
          </label>
          <label className="block text-sm">
            {t('settings.llmModelId')}
            <input
              className={inputCls}
              value={form.llm_model_id}
              onChange={(e) => set('llm_model_id', e.target.value)}
            />
          </label>
          <label className="block text-sm">
            {t('settings.llmBaseUrl')}
            <input
              className={inputCls}
              value={form.llm_api_base_url ?? ''}
              onChange={(e) => set('llm_api_base_url', e.target.value || null)}
            />
          </label>
          <label className="block text-sm">
            {t('settings.llmContextWindow')}
            <input
              type="number"
              className={inputCls}
              value={form.llm_context_window}
              onChange={(e) => set('llm_context_window', Number(e.target.value))}
            />
          </label>
        </div>
        <label className="block text-sm">
          {t('settings.llmKeyEnv')}
          <input
            className={inputCls}
            value={form.llm_api_key_env}
            onChange={(e) => set('llm_api_key_env', e.target.value)}
          />
        </label>
        <label className="block text-sm">
          {t('settings.llmKey', 'LLM API key')}
          <input
            type="password"
            className={inputCls}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={t('settings.llmKeyPlaceholder', 'sk-... (set to update server key, never shown again)')}
            autoComplete="off"
          />
        </label>
        <label className="block text-sm">
          {t('settings.hfEndpoint')}
          <input
            className={inputCls}
            value={hfEndpoint}
            onChange={(e) => setHfEndpoint(e.target.value)}
            placeholder={t('settings.hfEndpointPlaceholder', 'https://huggingface.co')}
          />
        </label>
        <label className="block text-sm">
          {t('settings.embeddingRoot')}
          <input
            className={inputCls}
            value={embeddingRoot}
            onChange={(e) => setEmbeddingRoot(e.target.value)}
            placeholder={t('settings.embeddingRootPlaceholder', '~/.cache/huggingface')}
          />
        </label>
        <p className="text-xs text-gf-muted">{t('settings.llmKeyHint')}</p>
      </section>

      {/* ── Save ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={submit}
          disabled={update.isPending}
          className="flex items-center gap-1.5 rounded-md bg-gf-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          <Save className="size-4" /> {t('common.save')}
        </button>
        {saved && <span className="text-xs text-gf-accent">{t('settings.saved')}</span>}
        {error && (
          <span className="text-xs text-gf-err" role="alert">
            {error}
          </span>
        )}
      </div>
    </div>
  )
}

/* ── Embedding Models sub-section ──────────────────────────────────────── */

function EmbeddingModelsSection({
  form,
  set,
  inputCls,
  offline,
}: {
  form: WorkspaceSettings
  set: <K extends keyof WorkspaceSettings>(key: K, value: WorkspaceSettings[K]) => void
  inputCls: string
  offline: boolean
}) {
  const { t } = useTranslation()
  const { data: models, isLoading: modelsLoading, refetch: refetchModels } = useModels()
  const download = useDownloadModel()

  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const backend = form.embedding_backend
  const isDense = backend === 'sentence-transformers' || backend === 'onnx'
  const activeTag = backend === 'onnx' ? 'onnx' : 'st'

  const filteredModels = (models ?? []).filter(
    (m) => m.backend === activeTag || !isDense,
  )

  const activeModelName = backend === 'onnx' ? form.onnx_model_name : form.st_model_name
  const activeSpaceId = isDense
    ? `text.${activeTag}.${(activeModelName ?? '').replace(/[/.]/g, '-').replace(/-+$/, '')}.v1`
    : null

  function handleDownload(modelName: string, modelBackend: 'st' | 'onnx') {
    setDownloadingId(modelName)
    download.mutate(
      { model_name: modelName, backend: modelBackend },
      {
        onSettled: () => setDownloadingId(null),
      },
    )
  }

  return (
    <section className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
      <h2 className="text-sm font-medium text-gf-muted">{t('settings.embeddings')}</h2>

      {/* Backend selector */}
      <label className="block text-sm">
        {t('settings.embeddingBackend')}
        <select
          className={inputCls}
          value={form.embedding_backend}
          onChange={(e) => set('embedding_backend', e.target.value)}
        >
          {EMBEDDING_BACKENDS.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
      </label>

      {/* Model name for the active backend */}
      {backend === 'onnx' && (
        <label className="block text-sm">
          {t('settings.onnxModelName')}
          <input
            className={inputCls}
            value={form.onnx_model_name}
            onChange={(e) => set('onnx_model_name', e.target.value)}
            placeholder="sentence-transformers/all-MiniLM-L6-v2"
          />
        </label>
      )}
      {backend === 'sentence-transformers' && (
        <label className="block text-sm">
          {t('settings.stModelName')}
          <input
            className={inputCls}
            value={form.st_model_name}
            onChange={(e) => set('st_model_name', e.target.value)}
            placeholder="sentence-transformers/all-MiniLM-L6-v2"
          />
        </label>
      )}

      {/* Active space id badge */}
      {activeSpaceId && (
        <p className="text-xs text-gf-muted">
          {t('settings.activeSpaceId')}: <code className="font-mono">{activeSpaceId}</code>
        </p>
      )}

      {/* Hub model list */}
      {isDense && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-gf-muted">{t('settings.hubModels')}</p>
            <button
              type="button"
              disabled={modelsLoading}
              onClick={() => void refetchModels()}
              className="flex items-center gap-1 text-xs text-gf-accent hover:underline disabled:opacity-50"
              data-testid="scan-models-btn"
            >
              <RefreshCw className={cn('size-3', modelsLoading && 'animate-spin')} />
              {t('settings.scanModels', 'Scan Models')}
            </button>
          </div>
          {filteredModels.length === 0 ? (
            <p className="text-xs text-gf-muted">{t('settings.noHubModels')}</p>
          ) : (
            <div className="space-y-1">
              {filteredModels.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center justify-between gap-3 rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{m.name}</div>
                    <div className="flex gap-2 text-xs text-gf-muted">
                      <span>{formatBytes(m.size_bytes)}</span>
                      <span className={m.downloaded ? 'text-green-600' : 'text-gf-muted'}>
                        {m.downloaded ? t('settings.downloaded') : t('settings.notDownloaded')}
                      </span>
                      {m.space_id && (
                        <span className="font-mono text-[10px]">{m.space_id}</span>
                      )}
                    </div>
                  </div>
                  {!m.downloaded && (
                    <button
                      type="button"
                      disabled={offline || downloadingId === m.name}
                      onClick={() =>
                        handleDownload(m.name, m.backend as 'st' | 'onnx')
                      }
                      className="shrink-0 flex items-center gap-1 rounded-md border border-gf-border px-2 py-1 text-xs hover:bg-gf-border disabled:opacity-50"
                    >
                      <Download className="size-3" />
                      {downloadingId === m.name
                        ? t('settings.downloading')
                        : t('settings.download')}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
          {offline && (
            <p className="text-xs text-gf-err">{t('settings.offlineHint')}</p>
          )}
        </div>
      )}
    </section>
  )
}

function VisionModelsSection({
  form,
  offline,
}: {
  form: WorkspaceSettings
  offline: boolean
}) {
  const { t } = useTranslation()
  const download = useVisionDownloadModel()
  const [jobId, setJobId] = useState<string | null>(null)
  const { data: job } = useJobPolling(jobId)

  const isRunning = download.isPending || job?.status === 'pending' || job?.status === 'running'
  const isSuccess = job?.status === 'completed'
  const isError = job?.status === 'failed' || job?.status === 'error'

  function handleDownload() {
    setJobId(null)
    download.mutate(undefined, {
      onSuccess: (resp) => setJobId(resp.job_id),
    })
  }

  return (
    <section className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
      <h2 className="text-sm font-medium text-gf-muted">{t('settings.visionModels', 'Vision Models')}</h2>
      {form.vision_path ? (
        <p className="text-xs text-gf-muted">
          {t('settings.visionPathCurrent', 'Vision model ready:')} <code>{form.vision_path}</code>
        </p>
      ) : (
        <>
          <p className="text-xs text-gf-muted">
            {t('settings.visionHint', 'Download OLMoEarth Nano v1.2 weights on first use.')}
          </p>
          <button
            type="button"
            disabled={offline || isRunning}
            onClick={handleDownload}
            title={offline ? t('settings.offlineHint') : undefined}
            className="flex items-center gap-1.5 rounded-md bg-gf-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            {isRunning ? <Loader2 className="size-3.5 animate-spin" /> : <Download className="size-3.5" />}
            {isRunning ? t('settings.downloading') : t('settings.downloadOlmoEarth', 'Download OLMoEarth')}
          </button>
          {offline && <p className="text-xs text-gf-err">{t('settings.offlineHint')}</p>}
          {isError && <p className="text-xs text-gf-err">{t('settings.downloadFailed', 'Download failed.')}</p>}
          {isSuccess && (
            <p className="text-xs text-gf-ok">
              <CheckCircle2 className="inline size-3.5" /> {t('settings.downloadDone', 'Download complete.')}
            </p>
          )}
        </>
      )}
    </section>
  )
}
