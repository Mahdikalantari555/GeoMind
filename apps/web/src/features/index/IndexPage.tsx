import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Database, Download, Layers, RefreshCw } from 'lucide-react'
import { useBuildIndex, useIndexManifest, useRebuildIndex } from './hooks'
import { useModels, useDownloadModel, formatBytes } from '../workspace/modelHooks'

export function IndexPage() {
  const { t } = useTranslation()
  const build = useBuildIndex()
  const rebuild = useRebuildIndex()
  const { data: manifestData, isLoading: manifestLoading } = useIndexManifest()
  const { data: models } = useModels()
  const download = useDownloadModel()
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  function handleDownload(modelName: string, backend: 'st' | 'onnx') {
    setDownloadingId(modelName)
    download.mutate(
      { model_name: modelName, backend },
      { onSettled: () => setDownloadingId(null) },
    )
  }

  const manifest = manifestData?.manifest
  const activeSpace = manifestData?.space_id ?? 'default'

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('nav.index')}</h1>

      {/* ── Active Space & Manifest Info ─────────────────────── */}
      <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Layers className="size-4 text-gf-accent" />
            <h2 className="text-sm font-semibold">{t('index.manifestTitle')}</h2>
          </div>
          <span
            dir="ltr"
            data-testid="index-active-space"
            className="rounded px-2 py-0.5 text-xs font-mono font-medium bg-gf-border text-gf-text"
          >
            {activeSpace}
          </span>
        </div>

        {manifestLoading ? (
          <p className="text-sm text-gf-muted">Loading manifest…</p>
        ) : manifest ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div className="rounded border border-gf-border/60 bg-gf-bg p-2.5">
              <div className="text-xs text-gf-muted">{t('index.vectorCount')}</div>
              <div className="text-lg font-semibold mt-0.5" data-testid="index-vector-count">
                {manifest.doc_count ?? 0}
              </div>
            </div>
            <div className="rounded border border-gf-border/60 bg-gf-bg p-2.5">
              <div className="text-xs text-gf-muted">{t('index.dimension')}</div>
              <div className="text-lg font-semibold mt-0.5" data-testid="index-dimension">
                {manifest.dimension ?? '—'}
              </div>
            </div>
            <div className="rounded border border-gf-border/60 bg-gf-bg p-2.5 sm:col-span-2">
              <div className="text-xs text-gf-muted">{t('index.modelId')}</div>
              <div
                dir="ltr"
                className="text-xs font-mono truncate mt-1 text-start"
                title={manifest.model_id}
                data-testid="index-model-id"
              >
                {manifest.model_id ?? '—'}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gf-muted" data-testid="index-not-built">
            {t('index.notBuiltYet')}
          </p>
        )}
      </div>

      {/* ── Build / Rebuild ──────────────────────────────────── */}
      <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
        <p className="mb-4 text-sm text-gf-muted">
          {t('index.description')}
        </p>

        <div className="flex items-center gap-3">
          <button
            type="button"
            data-testid="build-index-btn"
            onClick={() => build.mutate(undefined)}
            disabled={build.isPending || rebuild.isPending}
            className="flex items-center gap-2 rounded-md bg-gf-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            <Database className="size-4" />
            {build.isPending ? t('index.building') : t('index.buildIndex')}
          </button>

          <button
            type="button"
            data-testid="rebuild-index-btn"
            onClick={() => rebuild.mutate(undefined)}
            disabled={build.isPending || rebuild.isPending}
            className="flex items-center gap-2 rounded-md border border-gf-border px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            <RefreshCw className="size-4" />
            {rebuild.isPending ? t('index.rebuilding') : t('index.rebuildIndex')}
          </button>
        </div>

        {build.isSuccess && (
          <p className="mt-3 text-xs text-green-600" data-testid="build-success">
            {t('index.builtSuccess', { space: build.data.space_id })}
          </p>
        )}
        {build.isError && (
          <p className="mt-3 text-xs text-gf-err" role="alert">
            {build.error.message}
          </p>
        )}
        {rebuild.isSuccess && (
          <p className="mt-3 text-xs text-green-600" data-testid="rebuild-success">
            {t('index.rebuiltSuccess', { space: rebuild.data.space_id })}
          </p>
        )}
        {rebuild.isError && (
          <p className="mt-3 text-xs text-gf-err" role="alert">
            {rebuild.error.message}
          </p>
        )}
      </div>

      {/* ── Embedding Model Hub ──────────────────────────────── */}
      {models && models.length > 0 && (
        <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
          <h2 className="mb-3 text-sm font-medium text-gf-muted">{t('index.hubTitle')}</h2>
          <div className="space-y-1">
            {models.map((m) => (
              <div
                key={m.id}
                className="flex items-center justify-between gap-3 rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{m.name}</div>
                  <div className="flex gap-2 text-xs text-gf-muted">
                    <span className="rounded px-1 py-0.5 text-[10px] font-medium bg-gf-border">
                      {m.backend}
                    </span>
                    <span>{formatBytes(m.size_bytes)}</span>
                    <span className={m.downloaded ? 'text-green-600' : 'text-gf-muted'}>
                      {m.downloaded ? t('settings.downloaded') : t('settings.notDownloaded')}
                    </span>
                  </div>
                </div>
                {!m.downloaded && (
                  <button
                    type="button"
                    disabled={downloadingId === m.name}
                    onClick={() => handleDownload(m.name, m.backend as 'st' | 'onnx')}
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
        </div>
      )}
    </div>
  )
}
