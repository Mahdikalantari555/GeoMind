import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Search } from 'lucide-react'

const PAGES = [
  { to: '/', labelKey: 'nav.overview' },
  { to: '/ask', labelKey: 'nav.ask' },
  { to: '/search', labelKey: 'nav.searchPage' },
  { to: '/ingest', labelKey: 'nav.ingest' },
  { to: '/maps', labelKey: 'nav.maps' },
  { to: '/collections', labelKey: 'nav.collections' },
  { to: '/assets', labelKey: 'nav.assets' },
  { to: '/index', labelKey: 'nav.index' },
  { to: '/feedback', labelKey: 'nav.feedback' },
  { to: '/eval', labelKey: 'nav.eval' },
  { to: '/agent', labelKey: 'nav.agentChat' },
  { to: '/conversations', labelKey: 'nav.conversations' },
  { to: '/tools', labelKey: 'nav.tools' },
  { to: '/playbooks', labelKey: 'nav.playbooks' },
  { to: '/farms', labelKey: 'nav.farms' },
  { to: '/settings', labelKey: 'nav.settings' },
  { to: '/doctor', labelKey: 'nav.doctor' },
  { to: '/knowledge/entities', labelKey: 'nav.entities' },
]

export function CommandPalette() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(true)
      } else if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (open) {
      setQuery('')
      setActive(0)
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [open])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return PAGES
    return PAGES.filter((p) => t(p.labelKey).toLowerCase().includes(q))
  }, [query, t])

  useEffect(() => {
    if (active >= filtered.length) setActive(0)
  }, [filtered, active])

  const select = (to: string) => {
    navigate(to)
    setOpen(false)
  }

  const onInputKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filtered[active]) select(filtered[active].to)
    }
  }

  if (!open) return null

  return (
    <div
      data-testid="command-palette"
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-24"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-lg rounded-lg border border-gf-border bg-gf-panel shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-gf-border px-3 py-2">
          <Search className="size-4 text-gf-muted" />
          <input
            ref={inputRef}
            data-testid="command-palette-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKey}
            placeholder={t('common.search', 'Search pages…')}
            className="w-full bg-transparent text-sm outline-none"
          />
        </div>
        <ul className="max-h-72 overflow-auto p-1">
          {filtered.map((p, i) => (
            <li key={p.to}>
              <button
                type="button"
                onClick={() => select(p.to)}
                className={cnBtn(i === active)}
              >
                {t(p.labelKey)}
              </button>
            </li>
          ))}
          {filtered.length === 0 && (
            <li className="px-3 py-2 text-sm text-gf-muted">No results</li>
          )}
        </ul>
      </div>
    </div>
  )
}

function cnBtn(active: boolean) {
  return `flex w-full items-center rounded-md px-3 py-2 text-sm text-start ${
    active ? 'bg-gf-accent-soft text-gf-accent' : 'text-gf-text hover:bg-gf-accent-soft/60'
  }`
}
