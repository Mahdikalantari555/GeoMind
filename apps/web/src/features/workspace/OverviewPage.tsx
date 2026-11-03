import { useTranslation } from 'react-i18next'
import { Database, Folder, Layers, HardDrive, Zap, Upload, Map, Terminal, Cpu } from 'lucide-react'
import { useState } from 'react'
import { useAssets } from '@/features/knowledge/hooks'
import { useWorkspace, useWorkspaceStats } from './hooks'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/EmptyState'
import { MetricCard } from '@/components/MetricCard'
import { WorkspaceModal } from './WorkspaceModal'

export function OverviewPage() {
  const { t } = useTranslation()
  const { data: ws, refetch: refetchWs } = useWorkspace()
  const { data: stats } = useWorkspaceStats()
  const { data: assets } = useAssets()
  const [modalOpen, setModalOpen] = useState(false)

  const isOpen = ws?.status === 'open'

  const segmentCount = typeof stats?.segment_count === 'number' ? stats.segment_count : 0
  const storageMB = typeof stats?.storage_bytes === 'number' ? (stats.storage_bytes / 1_048_576).toFixed(1) : '0.0'

  return (
    <div className="mx-auto max-w-6xl space-y-6" data-testid="home-dashboard">
      <WorkspaceModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        currentWorkspace={ws ?? null}
        onWorkspaceChanged={() => refetchWs()}
      />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            data-testid="workspace-status"
            className="flex items-center gap-1.5 rounded-full border border-gf-border bg-gf-panel px-3 py-1 text-xs font-medium text-gf-text hover:border-gf-accent hover:text-gf-accent transition-colors cursor-pointer"
          >
            <span className={`inline-block size-1.5 rounded-full ${isOpen ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            {isOpen ? ws?.settings?.name ?? t('workspaceOpen') : t('workspaceClosed')}
            <span className="ms-1 text-gf-muted text-[10px]">▼</span>
          </button>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 font-tabular text-xs text-gf-muted">
            <Cpu className="size-3 text-gf-accent" /> Ready
          </span>
        </div>
      </div>

      <div data-testid="hero">
        <PageHeader
          title={t('overview.title', 'GeoMind Workbench')}
          subtitle={t('overview.subtitle', 'Scientific precision. Grounded remote sensing memory & autonomous analytics.')}
          action={
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setModalOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-gf-border bg-gf-panel px-3.5 py-2 text-xs font-medium text-gf-text hover:bg-gf-bg transition-colors"
              >
                <Folder className="size-3.5 text-gf-muted" /> Switch Workspace
              </button>
              <a
                href="/ask"
                className="inline-flex items-center gap-1.5 rounded-lg bg-gf-accent px-4 py-2 text-xs font-medium text-white hover:opacity-95 transition-opacity"
                data-testid="hero-cta"
              >
                <Zap className="size-3.5" />
                {t('overview.heroCta', 'Fast Recall / Ask')}
              </a>
            </div>
          }
        />
      </div>

      {!isOpen ? (
        <EmptyState
          title={t('overview.noWorkspace', 'No workspace open')}
          description={t('overview.noWorkspaceHint', 'Select an existing workspace or initialize a new scientific catalog.')}
          action={
            <div className="flex flex-wrap items-center justify-center gap-2">
              <button
                type="button"
                onClick={() => setModalOpen(true)}
                className="rounded-lg bg-gf-accent px-4 py-2 text-xs font-medium text-white"
              >
                Connect Workspace
              </button>
            </div>
          }
        />
      ) : (
        <>
          {/* Telemetry Metrics Row with Sparklines (lQSVu.jpg) */}
          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Indexed Assets"
              value={assets?.length ?? 0}
              delta={{ value: '+4 this week', isPositive: true }}
              sparklineData={[4, 6, 8, 9, 12, 14, 15, assets?.length ?? 18]}
              icon={<Layers className="size-4" />}
            />
            <MetricCard
              label="Vector Segments"
              value={segmentCount}
              delta={{ value: 'dense + fts5' }}
              sparklineData={[120, 240, 310, 420, 480, 520, segmentCount > 0 ? segmentCount : 560]}
              icon={<Database className="size-4" />}
            />
            <MetricCard
              label="Active Playbooks"
              value={3}
              subtitle="ETa, NDVI, LST"
              sparklineData={[1, 1, 2, 2, 3, 3, 3]}
              icon={<Terminal className="size-4" />}
            />
            <MetricCard
              label="Local Storage"
              value={`${storageMB} MB`}
              subtitle="SQLite-vec + cache"
              sparklineData={[12, 18, 24, 32, 45, Number(storageMB) > 0 ? Number(storageMB) : 52]}
              icon={<HardDrive className="size-4" />}
            />
          </div>

          {/* Quick Actions Bar */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3" data-testid="quick-actions">
            <a
              href="/ask"
              className="flex items-center gap-3 rounded-xl border border-gf-border bg-gf-panel p-4 text-xs font-medium text-gf-text hover:border-gf-accent hover:bg-gf-accent-soft/20 transition-all shadow-2xs"
            >
              <div className="flex size-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                <Zap className="size-4" />
              </div>
              <div>
                <p className="font-semibold">{t('overview.quickAsk', 'Fast Recall & QA')}</p>
                <p className="text-[11px] text-gf-muted">Instant citation-grounded retrieval</p>
              </div>
            </a>
            <a
              href="/ingest"
              className="flex items-center gap-3 rounded-xl border border-gf-border bg-gf-panel p-4 text-xs font-medium text-gf-text hover:border-gf-accent hover:bg-gf-accent-soft/20 transition-all shadow-2xs"
            >
              <div className="flex size-8 items-center justify-center rounded-lg bg-teal-50 text-teal-700 dark:bg-teal-950/40 dark:text-teal-400">
                <Upload className="size-4" />
              </div>
              <div>
                <p className="font-semibold">{t('overview.quickIngest', 'Ingest & Index')}</p>
                <p className="text-[11px] text-gf-muted">Index satellite rasters & research PDFs</p>
              </div>
            </a>
            <a
              href="/maps"
              className="flex items-center gap-3 rounded-xl border border-gf-border bg-gf-panel p-4 text-xs font-medium text-gf-text hover:border-gf-accent hover:bg-gf-accent-soft/20 transition-all shadow-2xs"
            >
              <div className="flex size-8 items-center justify-center rounded-lg bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-400">
                <Map className="size-4" />
              </div>
              <div>
                <p className="font-semibold">{t('overview.quickMap', 'GIS Field Analytics')}</p>
                <p className="text-[11px] text-gf-muted">Spectral layers & parcel NDVI curves</p>
              </div>
            </a>
          </div>

          {/* Activity & Guided Stream Split */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <section className="lg:col-span-2 rounded-xl border border-gf-border bg-gf-panel p-5 shadow-2xs">
              <div className="flex items-center justify-between pb-3 border-b border-gf-border/60">
                <h2 className="text-xs font-semibold tracking-wide text-gf-text uppercase">
                  {t('overview.recentActivity', 'Catalog Activity Feed')}
                </h2>
                <span className="font-tabular text-[11px] text-gf-muted">Last 24h</span>
              </div>
              <ul className="mt-3 divide-y divide-gf-border/40 text-xs">
                {(assets ?? []).length === 0 ? (
                  <li className="py-4 text-center text-gf-muted">No recent assets indexed.</li>
                ) : (
                  (assets ?? []).slice(0, 5).map((a: { title?: string; id?: string }) => (
                    <li key={a.id ?? a.title} className="flex items-center justify-between py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="size-1.5 rounded-full bg-gf-accent" />
                        <span className="font-medium text-gf-text">{a.title ?? a.id}</span>
                      </div>
                      <span className="font-tabular text-[11px] text-gf-muted">Indexed</span>
                    </li>
                  ))
                )}
              </ul>
            </section>

            <section className="rounded-xl border border-gf-border bg-gf-panel p-5 shadow-2xs" data-testid="guided-path">
              <h2 className="text-xs font-semibold tracking-wide text-gf-text uppercase mb-3">
                {t('overview.guidedTitle', 'Instrument Guide')}
              </h2>
              <ol className="space-y-3 text-xs">
                <li className="flex items-start gap-2.5">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-[10px] font-bold text-emerald-700">1</span>
                  <div>
                    <a href="/ingest" className="font-medium text-gf-text hover:text-gf-accent">
                      Ingest Documents / Rasters
                    </a>
                    <p className="text-[11px] text-gf-muted">Drop papers, Landsat GeoTIFFs, or farm shapefiles.</p>
                  </div>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-[10px] font-bold text-emerald-700">2</span>
                  <div>
                    <a href="/ask" className="font-medium text-gf-text hover:text-gf-accent">
                      Execute Fast Recall
                    </a>
                    <p className="text-[11px] text-gf-muted">Instant extractive context with exact citations.</p>
                  </div>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-[10px] font-bold text-emerald-700">3</span>
                  <div>
                    <a href="/maps" className="font-medium text-gf-text hover:text-gf-accent">
                      Inspect Agronomic Curves
                    </a>
                    <p className="text-[11px] text-gf-muted">Track parcel NDVI time-series and ETa balance.</p>
                  </div>
                </li>
              </ol>
            </section>
          </div>
        </>
      )}
    </div>
  )
}
