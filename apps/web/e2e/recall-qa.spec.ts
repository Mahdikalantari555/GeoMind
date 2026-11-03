import { test, expect } from '@playwright/test'

test.describe('Dual-Mode Recall & Grounded QA Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/ask')
  })

  test('renders unified search bar and mode selectors', async ({ page }) => {
    await expect(page.getByTestId('unified-recall-qa')).toBeVisible()
    await expect(page.getByTestId('ask-form')).toBeVisible()
    await expect(page.getByText('Fast Recall')).toBeVisible()
    await expect(page.getByText('Grounded Synthesis')).toBeVisible()
  })

  test('toggles between fast recall and grounded QA mode', async ({ page }) => {
    // If SetupModal intercepts on closed workspace, dismiss or click directly
    const modal = page.getByTestId('setup-modal')
    if (await modal.isVisible()) {
      await modal.evaluate((el) => (el.style.display = 'none'))
    }
    const synthesisBtn = page.getByText('Grounded Synthesis')
    await synthesisBtn.click({ force: true })
    await expect(synthesisBtn).toHaveClass(/bg-gf-accent/)

    const recallBtn = page.getByText('Fast Recall')
    await recallBtn.click({ force: true })
    await expect(recallBtn).toHaveClass(/bg-gf-accent/)
  })

  test('disables input when workspace is closed and informs user', async ({ page }) => {
    const input = page.getByPlaceholder(/Ask a remote sensing question/i)
    await expect(input).toBeVisible()
    // When no workspace is open, input is disabled to maintain data sovereignty
    await expect(input).toBeDisabled()
  })
})
