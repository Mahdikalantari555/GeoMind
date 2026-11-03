import { NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Activity,
  BookOpen,
  Boxes,
  Bot,
  Map,
  Upload,
  Search,
  MessageSquare,
  Files,
  Database,
  ThumbsUp,
  Gauge,
  Wrench,
  ScrollText,
  MessagesSquare,
  LayoutDashboard,
  Tractor,
  ChevronDown,
  Home,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useMode } from '@/stores/mode'

type NavItem = {
  to: string
  labelKey: string
  icon: React.ComponentType<{ className?: string }>
  simple?: boolean
}

type NavGroup = { key: string; labelKey: string; items: NavItem[] }

const SIMPLE_CORE = new Set(['/', '/ask', '/search', '/ingest', '/maps'])

const GROUPS: NavGroup[] = [
  {
    key: 'knowledge',
    labelKey: 'nav.groupKnowledge',
    items: [
      { to: '/ask', labelKey: 'nav.ask', icon: MessageSquare, simple: true },
      { to: '/search', labelKey: 'nav.searchPage', icon: Search, simple: true },
      { to: '/ingest', labelKey: 'nav.ingest', icon: Upload, simple: true },
      { to: '/collections', labelKey: 'nav.collections', icon: Boxes },
      { to: '/assets', labelKey: 'nav.assets', icon: Files },
      { to: '/index', labelKey: 'nav.index', icon: Database },
      { to: '/feedback', labelKey: 'nav.feedback', icon: ThumbsUp },
      { to: '/eval', labelKey: 'nav.eval', icon: Gauge },
      { to: '/knowledge/entities', labelKey: 'nav.entities', icon: Database },
    ],
  },
  {
    key: 'geo',
    labelKey: 'nav.groupGeo',
    items: [
      { to: '/maps', labelKey: 'nav.maps', icon: Map, simple: true },
      { to: '/farms', labelKey: 'nav.farms', icon: Tractor },
    ],
  },
  {
    key: 'agent',
    labelKey: 'nav.groupAgent',
    items: [
      { to: '/agent', labelKey: 'nav.agentChat', icon: Bot },
      { to: '/conversations', labelKey: 'nav.conversations', icon: MessagesSquare },
      { to: '/tools', labelKey: 'nav.tools', icon: Wrench },
      { to: '/playbooks', labelKey: 'nav.playbooks', icon: ScrollText },
    ],
  },
]

const WORKSPACE_ITEMS: NavItem[] = [
  { to: '/', labelKey: 'nav.overview', icon: LayoutDashboard, simple: true },
  { to: '/settings', labelKey: 'nav.settings', icon: Wrench },
  { to: '/doctor', labelKey: 'nav.doctor', icon: Activity },
]

const HUB_COLLAPSE_KEY = 'gf.hubCollapsed'

function readCollapsed(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(HUB_COLLAPSE_KEY) || '{}')
  } catch {
    return {}
  }
}

function writeCollapsed(v: Record<string, boolean>) {
  try {
    localStorage.setItem(HUB_COLLAPSE_KEY, JSON.stringify(v))
  } catch {
    /* ignore */
  }
}

export function Sidebar() {
  const { t } = useTranslation()
  const { mode } = useMode()
  const simple = mode === 'simple'
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(() => {
    const base = readCollapsed()
    // Workspace collapsed by default
    if (base.workspace === undefined) base.workspace = true
    return base
  })

  useEffect(() => {
    writeCollapsed(collapsed)
  }, [collapsed])

  const toggleHub = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const isVisible = (item: NavItem) => (simple ? !!item.simple || SIMPLE_CORE.has(item.to) : true)

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col overflow-y-auto border-e border-gf-border bg-gf-panel">
      <div className="flex items-center gap-2 px-4 py-4">
        <BookOpen className="size-6 text-gf-accent" />
        <span className="text-lg font-semibold">{t('common.appName')}</span>
      </div>
      <nav className="flex flex-1 flex-col gap-4 px-2 pb-4">
        {/* Home */}
        <div>
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                isActive
                  ? 'bg-gf-accent-soft font-medium text-gf-accent'
                  : 'text-gf-text hover:bg-gf-accent-soft/60'
              )
            }
          >
            <Home className="size-4 shrink-0" />
            <span className="truncate">{t('nav.overview', 'Home')}</span>
          </NavLink>
        </div>

        {GROUPS.map((group) => {
          const items = group.items.filter(isVisible)
          if (items.length === 0) return null
          const isCollapsed = !!collapsed[group.key]
          return (
            <div key={group.key}>
              <button
                type="button"
                onClick={() => toggleHub(group.key)}
                className="flex w-full items-center justify-between px-2 pb-1 text-xs font-medium tracking-wide text-gf-muted uppercase"
                aria-expanded={!isCollapsed}
              >
                <span>{t(group.labelKey)}</span>
                <ChevronDown className={cn('size-3 transition-transform', isCollapsed && '-rotate-90')} />
              </button>
              {!isCollapsed && (
                <ul className="space-y-0.5">
                  {items.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        end={item.to === '/'}
                        className={({ isActive }) =>
                          cn(
                            'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                            isActive
                              ? 'bg-gf-accent-soft font-medium text-gf-accent'
                              : 'text-gf-text hover:bg-gf-accent-soft/60'
                          )
                        }
                      >
                        <item.icon className="size-4 shrink-0" />
                        <span className="truncate">{t(item.labelKey)}</span>
                      </NavLink>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}

        {/* Collapsible Workspace section */}
        <div>
          <button
            type="button"
            onClick={() => toggleHub('workspace')}
            className="flex w-full items-center justify-between px-2 pb-1 text-xs font-medium tracking-wide text-gf-muted uppercase"
            aria-expanded={!collapsed.workspace}
            data-testid="workspace-section-toggle"
          >
            <span>{t('nav.groupWorkspace')}</span>
            <ChevronDown className={cn('size-3 transition-transform', collapsed.workspace && '-rotate-90')} />
          </button>
          {!collapsed.workspace && (
            <ul className="space-y-0.5">
              {WORKSPACE_ITEMS.filter((i) => (simple ? i.simple : true) || i.to === '/settings' || i.to === '/doctor').map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                        isActive
                          ? 'bg-gf-accent-soft font-medium text-gf-accent'
                          : 'text-gf-text hover:bg-gf-accent-soft/60'
                      )
                    }
                  >
                    <item.icon className="size-4 shrink-0" />
                    <span className="truncate">{t(item.labelKey)}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          )}
        </div>
      </nav>
    </aside>
  )
}
