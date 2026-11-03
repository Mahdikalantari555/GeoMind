import { useTranslation } from 'react-i18next'
import { Database, Folder, Layers, HardDrive, Zap, Upload, Map } from 'lucide-react'
import { useState } from 'react'
import { useAssets, useCollections } from '@/features/knowledge/hooks'
import { useWorkspace, useWorkspaceStats } from './hooks'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/EmptyState'

export function OverviewPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const { data: stats } = useWorkspaceStats()
  const { data: collections } = useCollections()
  const { data: assets } = useAssets()
  const [showStats, setShowStats] = useState(false)

  const isOpen = ws?.status === 'open'

  const cards = [
    { icon: Folder, label: t('overview.collections'), value: collections?.length ?? 0 },
    { icon: Layers, label: t('overview.assets'), value: assets?.length ?? 0 },
    {
      icon: Database,
      label: t('overview.segments'),
      value: typeof stats?.segment_count === 'number' ? stats.segment_count : 0,
    },
    {
      icon: HardDrive,
      label: t('overview.storage'),
      value: typeof stats?.storage_bytes === 'number' ? `${(stats.storage_bytes / 1_048_576).toFixed(1)} MB` : '—',
    },
  ]

  return (
    <div className="mx-auto max-w-5xl space-y-6" data-testid="home-dashboard">
      <div className="flex items-center justify-between">
        <span data-testid="workspace-status" className="rounded-full border border-gf-border px-2.5 py-0.5 text-xs text-gf-muted">
          {isOpen ? ws?.settings?.name ?? t('workspaceOpen') : t('workspaceClosed')}
        </span>
      </div>
      <div data-testid="hero">
        <PageHeader
        title={t('overview.title', 'Home')}
        subtitle={t('overview.subtitle', 'Ask your data. Cited answers, no hallucination.')}
        action={
          <a
            href="/ask"
            className="inline-flex items-center gap-2 rounded-md bg-gf-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            data-testid="hero-cta"
          >
            <Zap className="size-4" />
            {t('overview.heroCta', 'Ask a question')}
          </a>
        }
      />
      </div>

      {!isOpen ? (
        <EmptyState
          title={t('overview.noWorkspace', 'No workspace open')}
          description={t('overview.noWorkspaceHint', 'Create in default Workspaces/ or open an existing workspace from the header.')}
          action={
            <div className="flex flex-wrap items-center justify-center gap-2">
              <a href="/ask" className="rounded-md border border-gf-border px-3 py-1.5 text-sm">{t('nav.ask')}</a>
              <a href="/ingest" className="rounded-md border border-gf-border px-3 py-1.5 text-sm">{t('nav.ingest')}</a>
              <a href="/maps" className="rounded-md border border-gf-border px-3 py-1.5 text-sm">{t('nav.maps')}</a>
            </div>
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3" data-testid="quick-actions">
            <a href="/ask" className="flex items-center gap-2 rounded-lg border border-gf-border bg-gf-panel p-4 text-sm font-medium hover:bg-gf-accent-soft/60">
              <Zap className="size-4 text-gf-accent" /> {t('overview.quickAsk', 'Ask')}
            </a>
            <a href="/ingest" className="flex items-center gap-2 rounded-lg border border-gf-border bg-gf-panel p-4 text-sm font-medium hover:bg-gf-accent-soft/60">
              <Upload className="size-4 text-gf-accent" /> {t('overview.quickIngest', 'Ingest docs')}
            </a>
            <a href="/maps" className="flex items-center gap-2 rounded-lg border border-gf-border bg-gf-panel p-4 text-sm font-medium hover:bg-gf-accent-soft/60">
              <Map className="size-4 text-gf-accent" /> {t('overview.quickMap', 'Map')}
            </a>
          </div>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {cards.map(({ icon: Icon, label, value }) => (
              <div key={label} className="rounded-lg border border-gf-border bg-gf-panel p-4">
                <Icon className="size-5 text-gf-accent" />
                <p className="mt-2 text-2xl font-semibold">{value}</p>
                <p className="text-xs text-gf-muted">{label}</p>
              </div>
            ))}
          </div>

          <section className="rounded-lg border border-gf-border bg-gf-panel p-4" data-testid="guided-path">
            <h2 className="mb-3 text-sm font-semibold">{t('overview.guidedTitle', 'Try in 5 minutes')}</h2>
            <ol className="space-y-2 text-sm">
              <li>
                <a href="/" className="text-gf-accent hover:underline">
                  {t('overview.step1', '1. Open or create a sample workspace')}
                </a>
              </li>
              <li>
                <a href="/ask" className="text-gf-accent hover:underline">
                  {t('overview.step2', '2. Ask a question')}
                </a>
              </li>
              <li>
                <a href="/ask" className="text-gf-accent hover:underline">
                  {t('overview.step3', '3. View the cited answer')}
                </a>
              </li>
            </ol>
          </section>

          <section className="rounded-lg border border-gf-border bg-gf-panel p-4">
            <h2 className="mb-2 text-sm font-medium text-gf-muted">{t('overview.recentActivity', 'Recent activity')}</h2>
            <ul className="space-y-1 text-sm text-gf-muted">
              {(assets ?? []).slice(0, 5).map((a: { title?: string; id?: string }) => (
                <li key={a.id ?? a.title}>{a.title ?? a.id}</li>
              ))}
              {(assets ?? []).length === 0 && <li>{t('overview.noActivity', 'No recent activity yet.')}</li>}
            </ul>
          </section>

          <div>
            <button
              type="button"
              onClick={() => setShowStats((s) => !s)}
              className="text-xs text-gf-muted hover:text-gf-text"
            >
              {showStats ? t('common.showLess') : t('overview.rawStats', 'Workspace stats (raw)')}
            </button>
            {showStats && (
              <pre dir="ltr" className="mt-2 max-h-72 overflow-auto rounded-md bg-gf-bg p-3 text-start font-mono text-xs">
                {JSON.stringify(stats ?? {}, null, 2)}
              </pre>
            )}
          </div>
        </>
      )}
    </div>
  )
}
