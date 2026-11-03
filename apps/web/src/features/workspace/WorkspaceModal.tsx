import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { workspaceApi, type WorkspaceStatus, type WorkspaceSuggestion } from '@/api/workspace'

interface WorkspaceModalProps {
  isOpen: boolean
  onClose: () => void
  currentWorkspace: WorkspaceStatus | null
  onWorkspaceChanged: () => void
}

export function WorkspaceModal({
  isOpen,
  onClose,
  currentWorkspace,
  onWorkspaceChanged,
}: WorkspaceModalProps) {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [suggestions, setSuggestions] = useState<WorkspaceSuggestion[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Creation form state
  const [newName, setNewName] = useState('')
  const [newPath, setNewPath] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    let active = true
    workspaceApi
      .listSuggestions()
      .then((res) => {
        if (active && res.suggestions) {
          setSuggestions(res.suggestions)
        }
      })
      .catch(() => {
        // graceful fallback if suggestions endpoint fails
      })
    return () => {
      active = false
    }
  }, [isOpen])

  if (!isOpen) return null

  const filtered = suggestions.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.path.toLowerCase().includes(search.toLowerCase())
  )

  const handleOpen = async (path: string) => {
    try {
      setLoading(true)
      setError(null)
      await workspaceApi.open({ path })
      onWorkspaceChanged()
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to open workspace')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newPath.trim()) return
    try {
      setCreating(true)
      setError(null)
      await workspaceApi.create({
        path: newPath.trim(),
        name: newName.trim() || 'Untitled Workspace',
        offline: false,
      })
      onWorkspaceChanged()
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create workspace')
    } finally {
      setCreating(false)
    }
  }

  const handleLoadDemo = async () => {
    try {
      setLoading(true)
      setError(null)
      const demoPath = '/tmp/geomind_demo_workspace'
      try {
        await workspaceApi.open({ path: demoPath })
      } catch {
        await workspaceApi.create({
          path: demoPath,
          name: 'Karkheh Basin (Demo)',
          offline: false,
        })
      }
      onWorkspaceChanged()
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load demo workspace')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      data-testid="workspace-modal-backdrop"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4"
      onClick={onClose}
    >
      <div
        data-testid="workspace-modal"
        className="flex h-[560px] w-full max-w-4xl overflow-hidden rounded-2xl border border-gf-border bg-gf-panel shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Left column: existing workspaces */}
        <div className="flex w-1/2 flex-col border-e border-gf-border bg-gf-bg/40 p-5">
          <div className="flex items-center justify-between pb-3">
            <h3 className="text-sm font-semibold tracking-wide text-gf-text uppercase">
              {t('workspaces.title', 'Workspaces')}
            </h3>
            <span className="font-tabular text-xs text-gf-muted">
              {suggestions.length} total
            </span>
          </div>

          <div className="relative mb-3">
            <input
              type="text"
              placeholder={t('workspaces.search', 'Filter workspaces...')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-gf-border bg-gf-panel px-3 py-1.5 text-xs text-gf-text placeholder-gf-muted outline-none focus:border-gf-accent focus:ring-1 focus:ring-gf-accent"
            />
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto pe-1">
            {filtered.length === 0 ? (
              <div className="py-8 text-center text-xs text-gf-muted">
                {t('workspaces.noWorkspaces', 'No workspaces found')}
              </div>
            ) : (
              filtered.map((item) => {
                const isActive = currentWorkspace?.path === item.path
                return (
                  <div
                    key={item.path}
                    onClick={() => handleOpen(item.path)}
                    className={`group flex cursor-pointer items-start justify-between rounded-xl border p-3 transition-colors ${
                      isActive
                        ? 'border-gf-accent bg-gf-accent-soft/30'
                        : 'border-gf-border/60 bg-gf-panel hover:border-gf-border hover:bg-gf-bg'
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gf-text">
                          {item.name || 'Untitled Workspace'}
                        </span>
                        {isActive && (
                          <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                            Active
                          </span>
                        )}
                      </div>
                      <p className="font-tabular text-xs text-gf-muted break-all">
                        {item.path}
                      </p>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Right column: create new or load demo */}
        <div className="flex w-1/2 flex-col justify-between p-6">
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-gf-text">
                {t('workspaces.createNew', 'Create or Connect Workspace')}
              </h3>
              <button
                type="button"
                onClick={onClose}
                className="text-gf-muted hover:text-gf-text"
              >
                ✕
              </button>
            </div>

            {error && (
              <div className="rounded-lg bg-rose-50 p-2.5 text-xs text-rose-700 dark:bg-rose-950/40 dark:text-rose-400">
                {error}
              </div>
            )}

            <form onSubmit={handleCreate} className="space-y-3.5">
              <div>
                <label className="mb-1 block text-xs font-medium text-gf-muted">
                  {t('workspaces.nameLabel', 'Workspace Name')}
                </label>
                <input
                  type="text"
                  placeholder="e.g. Zagros Forest Monitoring"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full rounded-lg border border-gf-border bg-gf-panel px-3 py-2 text-xs text-gf-text placeholder-gf-muted outline-none focus:border-gf-accent focus:ring-1 focus:ring-gf-accent"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-gf-muted">
                  {t('workspaces.pathLabel', 'Directory Path')} *
                </label>
                <input
                  type="text"
                  required
                  placeholder="/home/user/projects/my-geodata"
                  value={newPath}
                  onChange={(e) => setNewPath(e.target.value)}
                  className="w-full font-tabular rounded-lg border border-gf-border bg-gf-panel px-3 py-2 text-xs text-gf-text placeholder-gf-muted outline-none focus:border-gf-accent focus:ring-1 focus:ring-gf-accent"
                />
                <p className="mt-1 text-[11px] text-gf-muted">
                  Must be an absolute path on host filesystem.
                </p>
              </div>

              <button
                type="submit"
                disabled={creating || !newPath.trim()}
                className="w-full rounded-lg bg-gf-accent px-4 py-2 text-xs font-medium text-white transition-opacity hover:opacity-95 disabled:opacity-50"
              >
                {creating ? t('common.creating', 'Creating...') : t('workspaces.createButton', 'Initialize Workspace')}
              </button>
            </form>
          </div>

          {/* Quick Demo Section */}
          <div className="mt-6 rounded-xl border border-gf-border/80 bg-gf-bg/60 p-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-semibold text-gf-text">
                  New to GeoMind?
                </h4>
                <p className="mt-0.5 text-[11px] text-gf-muted">
                  Explore pre-indexed Landsat scenes, farm parcels, and ETa models in 1 click.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleLoadDemo}
              disabled={loading}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg border border-emerald-600/30 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800 transition-colors hover:bg-emerald-100/80 dark:bg-emerald-950/40 dark:text-emerald-300 dark:hover:bg-emerald-900/40"
            >
              <span>⚡</span> Load Demo Workspace (Karkheh Basin)
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
