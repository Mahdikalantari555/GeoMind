import { useEffect, useState } from 'react'
import { Sun, Moon } from 'lucide-react'

export function ThemeToggle() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
      const stored = localStorage.getItem('geomind-theme')
      if (stored === 'dark' || stored === 'light') return stored
      if (typeof window.matchMedia === 'function') {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      }
    }
    return 'light'
  })

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('geomind-theme', theme)
  }, [theme])

  const toggle = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))
  }

  return (
    <button
      type="button"
      data-testid="theme-toggle"
      onClick={toggle}
      className="flex size-7 items-center justify-center rounded-md border border-gf-border text-gf-muted hover:border-gf-accent hover:text-gf-text transition-colors"
      title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
      aria-label="Toggle theme"
    >
      {theme === 'light' ? <Moon className="size-3.5" /> : <Sun className="size-3.5" />}
    </button>
  )
}
