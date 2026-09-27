import { chromium } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const outputDir = path.resolve(rootDir, 'test-results/audit')
const screenshotsDir = path.resolve(outputDir, 'screenshots')

fs.mkdirSync(screenshotsDir, { recursive: true })

const ROUTES = [
  { path: '/', slug: 'overview' },
  { path: '/settings', slug: 'settings' },
  { path: '/doctor', slug: 'doctor' },
  { path: '/collections', slug: 'collections' },
  { path: '/knowledge/entities', slug: 'entities' },
  { path: '/ingest', slug: 'ingest' },
  { path: '/search', slug: 'search' },
  { path: '/ask', slug: 'ask' },
  { path: '/assets', slug: 'assets' },
  { path: '/index', slug: 'index' },
  { path: '/feedback', slug: 'feedback' },
  { path: '/eval', slug: 'eval' },
  { path: '/agent', slug: 'agent' },
  { path: '/conversations', slug: 'conversations' },
  { path: '/tools', slug: 'tools' },
  { path: '/playbooks', slug: 'playbooks' },
  { path: '/maps', slug: 'maps' },
  { path: '/farms', slug: 'farms' },
]

const LOCALES = ['en', 'fa']
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

async function ensureWorkspace() {
  try {
    const healthRes = await fetch('http://localhost:8000/api/v1/health')
    if (healthRes.ok) {
      const data = await healthRes.json()
      if (data.workspace?.status === 'closed') {
        console.log('Opening test workspace for crawl audit...')
        await fetch('http://localhost:8000/api/v1/workspace/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: '/tmp/audit-workspace', name: 'Audit Workspace' }),
        })
      }
    }
  } catch (err) {
    console.warn('Could not contact gateway to ensure workspace:', err.message)
  }
}

async function run() {
  console.log(`Starting crawl audit on ${BASE_URL}...`)
  await ensureWorkspace()

  const results = {
    timestamp: new Date().toISOString(),
    baseUrl: BASE_URL,
    totalRoutes: ROUTES.length,
    locales: LOCALES,
    routesVisited: 0,
    errors: [],
    warnings: [],
    networkFailures: [],
    pages: [],
  }

  for (const locale of LOCALES) {
    const browser = await chromium.launch({
      executablePath: '/usr/bin/chromium',
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    })

    const context = await browser.newContext({
      viewport: { width: 1280, height: 900 },
      locale: locale === 'fa' ? 'fa-IR' : 'en-US',
    })

    // Preload language in localStorage
    await context.addInitScript((loc) => {
      window.localStorage.setItem('gf.language', loc)
      if (document.documentElement) {
        document.documentElement.lang = loc
        document.documentElement.dir = loc === 'fa' ? 'rtl' : 'ltr'
      }
    }, locale)

    const page = await context.newPage()

    for (const route of ROUTES) {
      results.routesVisited++
      const targetUrl = `${BASE_URL}${route.path}`
      const pageRecord = {
        route: route.path,
        slug: route.slug,
        locale,
        url: targetUrl,
        consoleErrors: [],
        consoleWarns: [],
        failedRequests: [],
        screenshot: `${route.slug}-${locale}.png`,
        status: 'ok',
      }

      const onConsole = (msg) => {
        const type = msg.type()
        const text = msg.text()
        // Ignore React dev/act warnings in dev mode if any
        if (type === 'error') {
          pageRecord.consoleErrors.push(text)
          results.errors.push({ route: route.path, locale, message: text })
        } else if (type === 'warning') {
          pageRecord.consoleWarns.push(text)
          results.warnings.push({ route: route.path, locale, message: text })
        }
      }

      const onPageError = (err) => {
        const msg = err.message || String(err)
        pageRecord.consoleErrors.push(msg)
        results.errors.push({ route: route.path, locale, message: msg })
      }

      const onResponse = (resp) => {
        if (resp.status() >= 400) {
          const reqInfo = {
            url: resp.url(),
            status: resp.status(),
            statusText: resp.statusText(),
          }
          pageRecord.failedRequests.push(reqInfo)
          results.networkFailures.push({ route: route.path, locale, ...reqInfo })
        }
      }

      page.on('console', onConsole)
      page.on('pageerror', onPageError)
      page.on('response', onResponse)

      try {
        console.log(`[${locale.toUpperCase()}] Visiting ${route.path}...`)
        await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 10000 })
        await page.waitForTimeout(250)

        // Capture full-page screenshot
        const screenshotPath = path.resolve(screenshotsDir, `${route.slug}-${locale}.png`)
        await page.screenshot({ path: screenshotPath, fullPage: true })
      } catch (err) {
        pageRecord.status = 'error'
        pageRecord.consoleErrors.push(err.message || String(err))
        results.errors.push({ route: route.path, locale, message: err.message || String(err) })
      } finally {
        page.off('console', onConsole)
        page.off('pageerror', onPageError)
        page.off('response', onResponse)
      }

      results.pages.push(pageRecord)
    }

    await context.close()
    await browser.close()
  }

  const summaryPath = path.resolve(outputDir, 'summary.json')
  fs.writeFileSync(summaryPath, JSON.stringify(results, null, 2))
  console.log(`Audit crawl finished! Summary written to ${summaryPath}`)
  console.log(`Total errors: ${results.errors.length}`)
  console.log(`Total warnings: ${results.warnings.length}`)
  console.log(`Total network failures: ${results.networkFailures.length}`)

  return results
}

run().catch((e) => {
  console.error('Crawl script failed:', e)
  process.exit(1)
})
