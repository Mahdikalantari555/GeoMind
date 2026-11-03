import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/components/PageHeader'
import {
  Layers,
  Search,
  RefreshCw,
} from 'lucide-react'
import { useWorkspace } from '@/features/workspace/hooks'
import { useMaps, useGeoJson, useZonal } from './hooks'

export function MapsPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const [pattern] = useState('runs/**/*')
  const [filter, setFilter] = useState('')
  const { data, isLoading, error, refetch } = useMaps(pattern)

  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [opacity, setOpacity] = useState(85)

  const layers = data?.layers ?? []
  const filteredLayers = useMemo(() => {
    if (!filter.trim()) return layers
    const q = filter.toLowerCase()
    return layers.filter((l) => l.name.toLowerCase().includes(q) || l.kind.toLowerCase().includes(q))
  }, [layers, filter])

  const selectedLayer = useMemo(() => layers.find((l) => l.path === selectedPath) ?? null, [layers, selectedPath])
  const isVector = selectedLayer?.kind === 'vector' || selectedLayer?.ext === '.geojson' || selectedLayer?.name.endsWith('.geojson')
  const isTable = selectedLayer?.kind === 'table'

  const geoQuery = useGeoJson(isVector && selectedPath ? selectedPath : null)
  const zonalQuery = useZonal(isTable && selectedPath ? selectedPath : null)

  const isOpen = ws?.status === 'open'

  if (!isOpen) {
    return (
      <div className="mx-auto max-w-5xl space-y-5">
        <PageHeader title={t('maps.title', 'Maps & Field Analytics')} />
        <div className="rounded-xl border border-gf-border bg-gf-panel p-8 text-center">
          <p className="text-xs text-gf-muted">{t('maps.closed', 'Open a workspace to view geospatial map artifacts.')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col space-y-4" data-testid="gis-field-analytics">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gf-border/60 pb-3">
        <PageHeader
          title={t('maps.title', 'Geospatial Analytics & Maps')}
          subtitle="Precision remote sensing visualization, layer stacks, and zonal statistics."
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void refetch()}
            className="flex items-center gap-1.5 rounded-lg border border-gf-border bg-gf-panel px-3 py-1.5 text-xs font-medium text-gf-text hover:bg-gf-bg transition-colors"
          >
            <RefreshCw className="size-3 text-gf-muted" /> Refresh
          </button>
        </div>
      </div>

      {/* 3-Column Layout */}
      <div className="grid flex-1 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-12">
        {/* Left Column: Real Workspace Layers */}
        <div className="flex flex-col space-y-3 overflow-y-auto rounded-xl border border-gf-border bg-gf-panel p-4 shadow-2xs lg:col-span-4">
          <div className="flex items-center justify-between border-b border-gf-border/60 pb-2.5">
            <span className="text-xs font-semibold tracking-wide text-gf-text uppercase flex items-center gap-1.5">
              <Layers className="size-3.5 text-gf-accent" /> Workspace Layers
            </span>
            <span className="font-tabular text-[10px] text-gf-muted">{filteredLayers.length} total</span>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2 size-3 text-gf-muted" />
              <input
                type="text"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter layers..."
                className="w-full rounded-lg border border-gf-border bg-gf-bg ps-7 pe-2 py-1.5 text-xs outline-none focus:border-gf-accent"
              />
            </div>
          </div>

          <div className="flex-1 space-y-1.5 overflow-y-auto">
            {isLoading && <p className="text-xs text-gf-muted p-2">Loading catalog layers...</p>}
            {error && <p className="text-xs text-rose-600 p-2">Failed to load layers.</p>}
            {!isLoading && filteredLayers.length === 0 && (
              <p className="text-xs text-gf-muted p-4 text-center">No layers match the current pattern.</p>
            )}
            {filteredLayers.map((l) => {
              const isSelected = selectedPath === l.path
              return (
                <div
                  key={l.id || l.path}
                  onClick={() => setSelectedPath(l.path)}
                  className={`flex cursor-pointer items-center justify-between rounded-lg border p-2.5 text-xs transition-colors ${
                    isSelected
                      ? 'border-gf-accent bg-gf-accent-soft/30'
                      : 'border-gf-border/60 bg-gf-panel hover:bg-gf-bg'
                  }`}
                >
                  <div className="space-y-0.5 truncate pe-2">
                    <p className="font-medium text-gf-text truncate">{l.name || l.label}</p>
                    <p className="font-tabular text-[10px] text-gf-muted truncate">{l.path}</p>
                  </div>
                  <span className="font-tabular rounded bg-gf-bg border border-gf-border px-1.5 py-0.5 text-[9px] uppercase text-gf-muted">
                    {l.kind}
                  </span>
                </div>
              )
            })}
          </div>

          <div className="border-t border-gf-border/60 pt-3">
            <div className="flex items-center justify-between text-xs text-gf-muted">
              <span>Layer Opacity</span>
              <span className="font-tabular font-semibold text-gf-text">{opacity}%</span>
            </div>
            <input
              type="range"
              min={20}
              max={100}
              value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))}
              className="mt-2 w-full accent-gf-accent"
            />
          </div>
        </div>

        {/* Center: Map Canvas / Visualizer */}
        <div className="relative flex flex-col overflow-hidden rounded-xl border border-gf-border bg-slate-950 p-1 shadow-2xs lg:col-span-5">
          <div className="relative flex-1 rounded-lg overflow-hidden flex items-center justify-center bg-slate-900 border border-slate-800">
            <svg
              className="size-full max-h-[500px]"
              viewBox="0 0 600 450"
              preserveAspectRatio="xMidYMid meet"
              style={{ opacity: opacity / 100 }}
            >
              <defs>
                <pattern id="grid-pattern" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" strokeWidth="0.5" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="#090d16" />
              <rect width="100%" height="100%" fill="url(#grid-pattern)" />

              {/* Render dynamic polygons if GeoJSON is available or fall back to instrument wireframe */}
              {geoQuery.data?.geojson?.features ? (
                <g>
                  {(geoQuery.data.geojson.features as Array<{ id?: string }>).slice(0, 8).map((f, i) => {
                    const cx = 150 + (i % 3) * 140
                    const cy = 120 + Math.floor(i / 3) * 120
                    return (
                      <rect
                        key={f.id || i}
                        x={cx}
                        y={cy}
                        width="90"
                        height="70"
                        fill="#00876c"
                        fillOpacity="0.4"
                        stroke="#34d399"
                        strokeWidth="1.5"
                      />
                    )
                  })}
                </g>
              ) : (
                <g>
                  <polygon
                    points="140,110 320,90 350,230 180,260"
                    fill="#00876c"
                    fillOpacity="0.45"
                    stroke="#34d399"
                    strokeWidth="1.5"
                  />
                  <polygon
                    points="340,100 480,120 450,270 330,240"
                    fill="#0369a1"
                    fillOpacity="0.4"
                    stroke="#38bdf8"
                    strokeWidth="1.5"
                  />
                  <text x="220" y="180" fill="#f8fafc" fontSize="12" fontFamily="monospace">
                    {selectedLayer ? selectedLayer.name : 'Select a layer'}
                  </text>
                </g>
              )}
            </svg>

            <div className="absolute top-3 left-3 rounded-md bg-black/60 backdrop-blur-xs px-2.5 py-1 text-[11px] font-tabular text-white border border-white/10">
              {selectedLayer?.name ?? 'Spatial Canvas'} · {opacity}% Opacity
            </div>
          </div>
        </div>

        {/* Right Column: Inspector of Selected Layer / GeoJSON / Zonal */}
        <div className="flex flex-col space-y-4 rounded-xl border border-gf-border bg-gf-panel p-4 shadow-2xs lg:col-span-3">
          <div className="flex items-center justify-between border-b border-gf-border/60 pb-2.5">
            <span className="text-xs font-semibold tracking-wide text-gf-text uppercase">
              Layer Inspector
            </span>
            {selectedLayer && (
              <span className="font-tabular rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                {selectedLayer.kind}
              </span>
            )}
          </div>

          {!selectedLayer ? (
            <div className="flex flex-1 items-center justify-center text-center p-6 text-xs text-gf-muted">
              Select any layer from the left catalog to inspect attributes and metadata.
            </div>
          ) : (
            <div className="space-y-3 text-xs">
              <div>
                <p className="text-[10px] text-gf-muted uppercase tracking-wide">Identifier</p>
                <h4 className="font-semibold text-gf-text text-sm break-all">{selectedLayer.name}</h4>
              </div>

              <div className="space-y-1.5 border-t border-gf-border/60 pt-2.5">
                <p className="text-[10px] text-gf-muted uppercase">Filesystem Path</p>
                <p className="font-tabular break-all text-gf-text bg-gf-bg p-2 rounded border border-gf-border/60">
                  {selectedLayer.path}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2 border-y border-gf-border/60 py-2.5">
                <div>
                  <p className="text-[10px] text-gf-muted uppercase">Size</p>
                  <p className="font-tabular font-medium text-gf-text">
                    {(selectedLayer.size / 1024).toFixed(1)} KB
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-gf-muted uppercase">Extension</p>
                  <p className="font-tabular font-medium text-gf-text">{selectedLayer.ext}</p>
                </div>
              </div>

              {zonalQuery.data && (
                <div className="space-y-1">
                  <p className="text-[10px] text-gf-muted uppercase">Zonal Statistics</p>
                  <pre className="font-tabular max-h-36 overflow-auto rounded bg-gf-bg p-2 text-[10px] text-gf-text border border-gf-border/60">
                    {JSON.stringify(zonalQuery.data, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
