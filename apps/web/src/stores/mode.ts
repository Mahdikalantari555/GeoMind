import { useCallback, useEffect, useState } from 'react'

export type Mode = 'simple' | 'advanced'

const KEY = 'gf.mode'

export function readMode(): Mode {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'advanced' ? 'advanced' : 'simple'
  } catch {
    return 'simple'
  }
}

export function writeMode(m: Mode) {
  try {
    localStorage.setItem(KEY, m)
  } catch {
    /* ignore */
  }
}

export function useMode() {
  const [mode, setModeState] = useState<Mode>(() => readMode())
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === KEY) setModeState(readMode())
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])
  const setMode = useCallback((m: Mode) => {
    writeMode(m)
    setModeState(m)
  }, [])
  const toggle = useCallback(() => {
    setMode(mode === 'simple' ? 'advanced' : 'simple')
  }, [mode, setMode])
  return { mode, setMode, toggle, isSimple: mode === 'simple', isAdvanced: mode === 'advanced' }
}
