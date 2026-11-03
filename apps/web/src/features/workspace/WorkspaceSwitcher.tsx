import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FolderOpen, Plus, X, Layers, Zap } from 'lucide-react'
import { useCloseWorkspace, useCreateWorkspace, useOpenWorkspace, useWorkspace } from './hooks'
import { WorkspaceModal } from './WorkspaceModal'

export function WorkspaceSwitcher() {
  const { t } = useTranslation()
  const { data: ws, refetch } = useWorkspace()
  const open = useOpenWorkspace()
  const create = useCreateWorkspace()
  const close = useCloseWorkspace()
  const [path, setPath] = useState('')
  const [name, setName] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const dirInputRef = useRef<HTMLInputElement>(null)

  function pickDir() {
    dirInputRef.current?.click()
  }

  function onDirPicked(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return
    const entry = files[0] as File & { webkitRelativePath?: string }
    const rel = entry.webkitRelativePath ?? ''
    const dir = rel ? rel.split('/')[0] : ''
    if (dir) {
      const base = path.trim()
      setPath(base && !base.endsWith(dir) ? `${base.replace(/\/$/, '')}/${dir}` : dir)
    }
    e.target.value = ''
  }

  function submitOpen() {
    if (!path.trim()) return
    open.mutate({ path: path.trim() })
  }

  function submitCreate() {
    if (!name.trim()) return
    create.mutate({ path: path.trim(), name: name.trim(), offline: false })
  }

  function handleQuickDemo() {
    const demoPath = '/tmp/geomind_demo_workspace'
    open.mutate(
      { path: demoPath },
      {
        onError: () => {
          create.mutate({
            path: demoPath,
            name: 'Karkheh Basin (Demo)',
            offline: false,
          })
        },
      }
    )
  }

  const isOpen = ws?.status === 'open'

  return (
    <>
      <div className="flex flex-wrap items-center gap-1.5" data-testid="workspace-switcher">
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-1.5 rounded-lg border border-gf-border bg-gf-bg px-2.5 py-1 text-xs font-medium text-gf-text hover:border-gf-accent transition-colors"
          title="Open Workspace Manager"
        >
          <Layers className="size-3.5 text-gf-accent" />
          <span className="max-w-[120px] truncate sm:max-w-[180px]">
            {isOpen ? ws.settings?.name || ws.path?.split('/').pop() || 'Workspace' : t('workspace.manage', 'Workspaces')}
          </span>
          {isOpen && (
            <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
          )}
        </button>

        {!isOpen && (
          <button
            type="button"
            onClick={handleQuickDemo}
            className="flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20 transition-colors"
            title="Load demo data instant preview"
          >
            <Zap className="size-3" /> Demo
          </button>
        )}

        <FolderOpen className="size-4 shrink-0 text-gf-muted ms-1 hidden sm:inline" />
        <input
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder={t('workspace.pathPlaceholder')}
          className="w-28 rounded-md border border-gf-border bg-gf-bg px-2 py-1 text-xs outline-none focus:border-gf-accent sm:w-40 font-tabular"
          aria-label={t('workspace.pathPlaceholder')}
        />
        <button
          type="button"
          onClick={pickDir}
          title={t('workspace.browse')}
          className="shrink-0 rounded-md border border-gf-border px-2 py-1 text-xs hover:bg-gf-panel"
        >
          {t('workspace.browse')}
        </button>
        <input
          ref={dirInputRef}
          type="file"
          // @ts-expect-error non-standard dir-picking attribute
          webkitdirectory=""
          directory=""
          className="hidden"
          onChange={onDirPicked}
          data-testid="workspace-dir-input"
        />
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t('workspace.namePlaceholder')}
          className="w-24 rounded-md border border-gf-border bg-gf-bg px-2 py-1 text-xs outline-none focus:border-gf-accent sm:w-32"
          aria-label={t('workspace.namePlaceholder')}
        />
        <button
          type="button"
          onClick={submitOpen}
          disabled={open.isPending || !path.trim()}
          className="flex items-center gap-1 rounded-md border border-gf-border px-2.5 py-1 text-xs disabled:opacity-50 hover:bg-gf-panel"
        >
          {t('common.open')}
        </button>
        <button
          type="button"
          onClick={submitCreate}
          disabled={create.isPending || !name.trim()}
          title={!path.trim() ? 'Create in default Workspaces/' : undefined}
          className="flex items-center gap-1 rounded-md bg-gf-accent px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50"
        >
          <Plus className="size-3" /> {t('common.create')}
        </button>
        {isOpen && (
          <button
            type="button"
            onClick={() => close.mutate()}
            disabled={close.isPending}
            title={t('common.close')}
            className="rounded-md border border-gf-border p-1 text-gf-muted transition-colors hover:border-gf-err hover:text-gf-err disabled:opacity-50"
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>

      <WorkspaceModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        currentWorkspace={ws ?? null}
        onWorkspaceChanged={() => void refetch()}
      />
    </>
  )
}
