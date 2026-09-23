import { test, expect } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Key screen 1 (docs/phase-2/05-support-intake.md): Support files a report from
// a template, sees it in Support reports, and the triage lead finds it in the
// queue with a Support badge. Seed: backend/scripts/seed_e2e.py.

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)

test('support files a report that reaches the triage queue', async ({ browser }) => {
  const title = `Student can't join class ${Date.now()}`

  // ── Support ─────────────────────────────────────────────────────────────
  const supportCtx = await browser.newContext({ storageState: auth('support') })
  const page = await supportCtx.newPage()
  await page.goto('/support/new')
  const modal = page.getByRole('heading', { name: 'New report' }).locator('xpath=ancestor::div[contains(@class,"dialog-enter")]')
  await expect(modal).toBeVisible()

  // 1. Only projects with an active template are offered (same picker as New issue).
  //    With a single project and a single template, both are preselected.
  await modal.getByRole('button', { name: /E2E Product/ }).click()
  await expect(page.getByRole('button', { name: 'E2E Product', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'E2E Internal Tools', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'E2E Product', exact: true }).click()
  await expect(modal.getByText('Online class problem', { exact: true })).toBeVisible()
  await expect(modal.getByText('When the class started.')).toBeVisible()

  // 2. Submitting empty highlights the required fields.
  await modal.getByRole('button', { name: 'Submit report' }).click()
  await expect(modal.getByText('Give the report a title.')).toBeVisible()
  await expect(modal.getByText('This field is required.')).toBeVisible()

  // 3. Fill the fields and submit.
  await modal.getByLabel(/^Title/).fill(title)
  await modal.getByRole('button', { name: /^Date$/ }).click()
  await page.getByRole('button', { name: '15', exact: true }).click()
  await modal.getByLabel('Class time time').fill('18:30')
  await modal.getByText('Pick one…', { exact: true }).click()
  await page.getByRole('button', { name: 'iOS app' }).click()
  await modal.getByLabel('Class name', { exact: true }).fill('IELTS B2 — Evening')
  await modal.getByRole('button', { name: 'Submit report' }).click()
  await expect(modal).toBeHidden()

  // 4. The report appears in Support reports with status New.
  await expect(page).toHaveURL(/\/support\/reports/)
  const row = page.getByRole('row', { name: new RegExp(title) })
  await expect(row).toBeVisible()
  await expect(row.getByText('New', { exact: true })).toBeVisible()
  await supportCtx.close()

  // ── 5. The triage lead (E2E QA) sees it in the queue with a Support badge ──
  const leadCtx = await browser.newContext({ storageState: auth('qa') })
  const lead = await leadCtx.newPage()
  await lead.goto('/triage')
  const item = lead.getByRole('listitem').filter({ hasText: title })
  await expect(item).toBeVisible()
  await expect(item.getByText('Support', { exact: true })).toBeVisible()
  await leadCtx.close()
})
