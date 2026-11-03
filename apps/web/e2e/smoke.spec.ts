import { test, expect } from '@playwright/test'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

// Playwright needs a Chromium binary to run the E2E suite. When none is
// installed (no root to apt-install, CDN geo-blocked), skip the suite
// cleanly instead of failing the whole run.
const browserCandidates = [
  resolve('node_modules/.local-browsers/chromium/chrome-linux64/chrome'),
  resolve('/usr/bin/chromium'),
  resolve('/usr/bin/chromium-browser'),
  resolve('/usr/bin/google-chrome'),
]
const hasBrowser = browserCandidates.some(existsSync)

test.describe('M7 smoke', () => {
  test.skip(!hasBrowser, 'No Chromium binary installed')

  test('workspace → ingest → search → ask (abstention)', async ({ page }) => {
    // ── Mock gateway ──────────────────────────────────────────────────
    let wsOpen = false
    const collections: { id: string; name: string }[] = []
    const assets: unknown[] = []

    await page.route('**/api/v1/**', async (route) => {
      const req = route.request()
      const url = new URL(req.url())
      const path = url.pathname.replace('/api/v1', '')
      const method = req.method()

      const json = (body: unknown, status = 200) =>
        route.fulfill({
          status,
          contentType: 'application/json',
          body: JSON.stringify(body),
        })

      // health — gateway up + workspace closed/open + llm missing (abstention)
      if (path === '/health') {
        return json({
          status: 'ok',
          workspace: wsOpen ? 'open' : 'closed',
          path: wsOpen ? '/tmp/ws' : null,
          llm: { provider: 'api', configured: false, reachable: false },
          version: '0.1.0',
        })
      }

      if (path.startsWith('/workspace')) {
        if (path === '/workspace' && method === 'GET') {
          return json(
            wsOpen
              ? { status: 'open', path: '/tmp/ws', settings: { name: 'Smoke WS', language: 'en' } }
              : { status: 'closed', path: null },
          )
        }
        if (path === '/workspace/stats' && method === 'GET') {
          return wsOpen
            ? json({ asset_count: assets.length, segment_count: 0, storage_bytes: 0 })
            : json({ error: { code: 'workspace_not_open', message: 'No workspace is open.' } }, 409)
        }
        if (path === '/workspace/settings' && method === 'PUT') {
          return json({ name: 'Smoke WS', language: 'en' })
        }
      }

      if (path === '/workspace/create' && method === 'POST') {
        wsOpen = true
        collections.length = 0
        return json({ status: 'open', path: '/tmp/ws' }, 201)
      }
      if (path === '/workspace/open' && method === 'POST') {
        wsOpen = true
        return json({ status: 'open', path: '/tmp/ws' })
      }
      if (path === '/workspace/close' && method === 'POST') {
        wsOpen = false
        return json({ status: 'closed' })
      }

      // collections
      if (path === '/collections' && method === 'GET') {
        return wsOpen ? json(collections) : json({ error: { code: 'workspace_not_open', message: '' } }, 409)
      }
      if (path === '/collections' && method === 'POST') {
        const body = req.postDataJSON() as { name: string }
        const col = { id: `col_${collections.length + 1}`, name: body.name, description: null }
        collections.push(col)
        return json(col, 201)
      }

      // ingest — return 202 job
      if (path === '/ingest' && method === 'POST') {
        return json({ job_id: 'job_smoke', status: 'queued' }, 202)
      }
      if (path.startsWith('/jobs/')) {
        return json({ id: 'job_smoke', type: 'ingest', status: 'completed', progress: 1, result: { asset_id: 'asset_1', segment_count: 3 } })
      }

      // assets
      if (path.startsWith('/assets')) {
        return json(assets)
      }

      // search — return 1 hit
      if (path === '/search' && method === 'POST') {
        return json({
          hits: [
            {
              id: 'seg_1',
              score: 0.92,
              sparse_score: 0.5,
              dense_score: 0.42,
              text: 'Sugarcane NDVI stress threshold is 0.4 (severe below).',
              locator: { file: 'doc.pdf', page: 1 },
              metadata: {},
            },
          ],
          total: 1,
          took_ms: 12,
        })
      }

      // ask — abstention (LLM unavailable)
      if (path === '/ask' && method === 'POST') {
        return json({
          answer: '',
          citations: [],
          abstained: true,
          abstention_reason: 'LLM unavailable — no API key configured.',
        })
      }

      // doctor — realistic payload: optional dep chips, LLM probe (key missing)
      if (path === '/doctor') {
        return json({
          environment: {
            python_version: '3.11.9',
            python_ok: true,
            core_ok: true,
            optional_deps: { Pillow: true, rasterio: true, torch: false },
          },
          workspace: { ok: true, closed: false, checks: {} },
          workspace_open: { ok: true, checks: {} },
          diagnostics: {
            llm: {
              provider: 'api',
              model_id: 'kilo-auto/free',
              base_url: 'https://api.kilo.ai/api/gateway/v1',
              key_env: 'GEOMEMORY_LLM_API_KEY',
              key_configured: false,
              context_window: 8192,
            },
          },
          embedding: {
            hub_count: 1,
            downloaded: 0,
            active_backend: 'onnx',
            active_model: 'Xenova/all-MiniLM-L6-v2',
          },
          resolved_workspace_root: '/tmp/ws',
        })
      }
      if (path === '/doctor/llm') {
        return json({
          provider: 'api',
          model_id: 'kilo-auto/free',
          base_url: 'https://api.kilo.ai/api/gateway/v1',
          key_env: 'GEOMEMORY_LLM_API_KEY',
          key_set: false,
          context_window: 8192,
        })
      }
      if (path.startsWith('/index') || path.startsWith('/feedback')) {
        return json({})
      }
      // setup-modal compute config + model discovery
      if (path === '/environment/overrides') {
        return method === 'POST' ? json({ applied: {}, ignored: [] }) : json({})
      }
      if (path === '/models') return json([])
      // agent stubs
      if (path.startsWith('/agent')) {
        if (path === '/agent/tools' || path === '/agent/tools/') return json({ tools: [{ name: 'geo_search', description: 'search', params: {}, returns: '', timeout_s: 30, cacheable: false }] })
        if (path === '/agent/conversations' || path.startsWith('/agent/files')) return json({ conversations: [], files: [], pattern: '' })
        if (path === '/agent/playbooks') return json({ playbooks: [] })
        if (path.startsWith('/agent/farms')) return json({ farms: [], count: 0, source: null, reports: [] })
        if (path.startsWith('/agent/maps')) return json({ artifacts: [], layers: [], count: 0, pattern: '', legend: null })
      }

      // SSE — empty
      if (path === '/events') {
        return route.fulfill({ status: 200, contentType: 'text/event-stream', body: 'data: ping\n\n' })
      }

      return route.continue()
    })

    // health + openapi
    await page.route('**/openapi.json', async (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ openapi: '3.0.0', info: { title: 'x', version: '0.1' }, paths: {} }) }),
    )

    await page.addInitScript(() => localStorage.setItem('gf.mode', 'advanced'))

    // ── Flow ──────────────────────────────────────────────────────────
    await page.goto('/')

    // App shell renders, health pill shows gateway online
    await expect(page.getByTestId('app-shell')).toBeVisible()
    // Overview title
    await expect(page.getByRole('heading', { name: /Overview|نمای کلی/ })).toBeVisible()

    // First-run setup modal blocks the UI until a workspace exists
    const modal = page.getByTestId('setup-modal')
    await expect(modal).toBeVisible()
    await modal.getByPlaceholder(/Workspace name|نام فضای کاری/).fill('Smoke WS')
    await modal.getByPlaceholder(/\/path\/to\/workspace|\/مسیر/).fill('/tmp/ws')
    await modal.getByRole('button', { name: /^Create$|^ایجاد$/ }).click()
    await expect(modal).not.toBeVisible({ timeout: 5_000 })

    // Workspace switcher in header reflects open workspace
    await expect(page.getByTestId('workspace-switcher')).toBeVisible()
    await expect(page.getByTestId('workspace-status')).toContainText(/Smoke WS|open/i, { timeout: 5_000 })

    // Screenshot at overview
    await page.screenshot({ path: 'screenshots/overview.png' })

    await page.getByTestId('workspace-section-toggle').click()

    // Settings — save with sqlite-vec (must not 422)
    await page.getByRole('link', { name: /Settings| تنظیمات/ }).click()
    const saveBtn = page.getByRole('button', { name: /Save|ذخیره/ })
    await saveBtn.click()
    await expect(page.getByText(/Saved|ذخیره شد/)).toBeVisible({ timeout: 5_000 })
    await page.screenshot({ path: 'screenshots/settings.png' })

    // Doctor — optional deps render, no [object Object], no GGUF path
    await page.getByRole('link', { name: /Doctor| عیب‌یابی/ }).click()
    await expect(page.getByText('Pillow')).toBeVisible({ timeout: 5_000 })
    const doctorText = (await page.locator('body').textContent()) ?? ''
    expect(doctorText).not.toContain('[object Object]')
    expect(doctorText).not.toMatch(/GGUF path/i)
    await page.screenshot({ path: 'screenshots/doctor.png' })

    // Collections — create one
    await page.getByRole('link', { name: /Collections|مجموعه/ }).click()
    await page.getByRole('button', { name: /New collection|مجموعه جدید/ }).first().click()
    const nameInput = page.getByTestId('collection-name')
    await nameInput.fill('smoke-docs')
    await page.getByTestId('collection-form').getByRole('button', { name: /Create|ایجاد/ }).click()
    await expect(page.getByText('smoke-docs')).toBeVisible({ timeout: 5_000 })

    // Ingest — smoke that ingest page renders (file upload is mocked)
    await page.getByRole('link', { name: /Ingest|ورود داده/ }).click()
    await expect(page.getByRole('heading', { name: /Ingest|ورود داده/ })).toBeVisible()

    // Search — run query and see hit
    await page.getByRole('link', { name: /^Search|جستجو/ }).click()
    const searchInput = page.getByPlaceholder(/Search the workspace|جستجو در فضای کاری/)
    await searchInput.fill('NDVI stress')
    // click Search button (there are two: header nav and filter bar) — use the one in search page
    await page.getByRole('button', { name: /^Search$|^جستجو$/ }).last().click()
    await expect(page.getByText(/Sugarcane NDVI/)).toBeVisible({ timeout: 5_000 })

    // Ask — abstention path
    await page.getByRole('link', { name: /Ask|پرسش/ }).click()
    const askInput = page.getByPlaceholder(/Ask a question|سؤال خود را/)
    await askInput.fill('What is the NDVI threshold for sugarcane stress?')
    await page.getByRole('button', { name: /Send|ارسال/ }).click()
    await expect(page.getByText(/No answer provided|پاسخی ارائه نشد/)).toBeVisible({ timeout: 5_000 })
    await expect(page.getByText(/LLM unavailable|مدل زبانی/)).toBeVisible()

    // RTL flip — en → fa → en
    // toggle to fa
    const faBtn = page.getByRole('button', { name: /FA|فارسی/ })
    if (await faBtn.isVisible()) {
      await faBtn.click()
      await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
      // flip back to en
      await page.getByRole('button', { name: /EN|English/ }).click()
      await expect(page.locator('html')).toHaveAttribute('dir', 'ltr')
    }

    // Maps + Farms render empty states without crashing
    await page.getByRole('link', { name: /Maps|نقشه/ }).click()
    await expect(page.getByRole('heading', { name: /Maps|نقشه/ })).toBeVisible()
    await page.getByRole('link', { name: /Farms|مزارع/ }).click()
    await expect(page.getByRole('heading', { name: /Farms|مزارع/ })).toBeVisible()

    // A11y sanity: every page has a single h1
    await expect(page.locator('h1')).toHaveCount(1)
  })
})
