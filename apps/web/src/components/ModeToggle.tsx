import { useMode } from '@/stores/mode'

export function ModeToggle() {
  const { mode, toggle } = useMode()
  return (
    <button
      type="button"
      data-testid="mode-toggle"
      onClick={toggle}
      className="rounded-md border border-gf-border px-2 py-1 text-xs font-medium text-gf-text hover:bg-gf-accent-soft/60"
      aria-label="Toggle simple or advanced mode"
    >
      {mode === 'simple' ? 'Simple' : 'Advanced'}
    </button>
  )
}
