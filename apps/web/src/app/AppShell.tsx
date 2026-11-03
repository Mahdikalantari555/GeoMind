import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { HealthPill } from './HealthPill'
import { LanguageToggle } from './LanguageToggle'
import { ThemeToggle } from '@/components/ThemeToggle'
import { CommandPalette } from '@/components/CommandPalette'
import { useEvents } from './useEvents'
import { useWorkspace } from '@/features/workspace/hooks'
import { WorkspaceSwitcher } from '@/features/workspace/WorkspaceSwitcher'
import { SetupModal } from '@/features/workspace/SetupModal'

export function AppShell() {
  const { error: eventsError } = useEvents()
  const { data: workspace } = useWorkspace()
  const isOpen = workspace?.status === 'open'
  return (
    <div className="flex h-screen overflow-hidden" data-testid="app-shell">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-gf-border bg-gf-panel px-4 py-2">
          <WorkspaceSwitcher />
          <div className="flex shrink-0 items-center gap-2">
            <HealthPill />
            <ThemeToggle />
            <LanguageToggle />
          </div>
        </header>
        {eventsError && (
          <div className="flex items-center justify-between gap-3 bg-gf-err/10 px-4 py-1.5 text-xs text-gf-err" role="alert">
            <span>{eventsError}</span>
            <button type="button" onClick={() => window.location.reload()} className="rounded border border-gf-err px-2 py-0.5">
              Retry
            </button>
          </div>
        )}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      <CommandPalette />
      </div>
      {!isOpen && <SetupModal />}
    </div>
  )
}

