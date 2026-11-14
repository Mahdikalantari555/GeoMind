// Node 26+ ships a global localStorage stub that is undefined without
// --localstorage-file, and vitest 4 + jsdom 30 no longer populate it in
// every environment. Provide a minimal in-memory implementation for tests.
if (typeof globalThis.localStorage === "undefined") {
  const store = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (k: string) => (store.has(k) ? (store.get(k) as string) : null),
    key: (i: number) => ([...store.keys()][i] as string | undefined) ?? null,
    removeItem: (k: string) => {
      store.delete(k);
    },
    setItem: (k: string, v: string) => {
      store.set(k, String(v));
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: storage,
    configurable: true,
  });
}

import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  // Defensive: some CI environments (node fallback) have no localStorage.
  globalThis.localStorage?.clear()
})
