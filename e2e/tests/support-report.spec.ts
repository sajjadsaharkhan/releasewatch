import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Key screen 1 (docs/phase-2/05-support-intake.md): Support files a report from
// a template, sees it in Support reports, and the triage lead finds it in the
// queue with a Support badge. The slice-14 scenario records a recurrence from
// the similar-reports panel instead of filing a duplicate (14, AC-S09). Seed:
// backend/scripts/seed_e2e.py (open support report "Emoji reactions…", fake Jev
// answering "same").

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)

async function api(page: Page, method: string, url: string, body?: unknown) {
  return page.evaluate(async ({ method, url, body }) => {
    const res = await fetch(`/api/v1${url}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('rw:token')}`,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!res.ok) throw new Error(`${method} ${url} → ${res.status} ${await res.text()}`)
    return res.json()
  }, { method, url, body })
}

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

test('record recurrence from the similar reports panel', async ({ browser }) => {
  const title = 'Emoji reactions in group chat disappear after refresh again'

  // The seeded open support report about the same problem.
  const supportCtx = await browser.newContext({ storageState: auth('support') })
  const page = await supportCtx.newPage()
  await page.goto('/inbox')
  const seeded = (await api(page, 'GET', '/issues?statuses=new&search='
    + encodeURIComponent('Emoji reactions in group chat'))).items
    .find((i: { title: string }) => i.title.startsWith('Emoji reactions in group chat'))
  expect(seeded, 'the seeded open support report exists').toBeTruthy()

  // ── 1. The panel appears once the title and a template text field are filled ──
  await page.goto('/support/new')
  const modal = page.getByRole('heading', { name: 'New report' }).locator('xpath=ancestor::div[contains(@class,"dialog-enter")]')
  await expect(modal).toBeVisible()
  await modal.getByLabel(/^Title/).fill(title)
  await modal.getByLabel('Class name', { exact: true }).fill('IELTS B2 — Evening')
  const panel = page.getByTestId('similar-reports')
  await expect(panel).toBeVisible() // after the 800 ms debounce
  const row = panel.getByRole('listitem').filter({ hasText: 'Emoji reactions in group chat' })
  await expect(row).toBeVisible()
  const record = row.getByRole('button', { name: 'This is the same problem' })

  // ── 2. The button stays disabled until the required fields are filled ──────
  await expect(record).toBeDisabled()
  await modal.getByRole('button', { name: /^Date$/ }).click()
  await page.getByRole('button', { name: '15', exact: true }).click()
  await modal.getByLabel('Class time time').fill('18:30')
  await expect(record).toBeEnabled()

  // ── 3. The confirmation shows the composed content that will be added ─────
  await record.click()
  const preview = page.getByTestId('recurrence-preview')
  // The preview shows the exact markdown that will be recorded.
  await expect(preview).toContainText('**Report template:** Online class problem')
  await expect(preview).toContainText(/- \*\*Class time:\*\* \S+ 18:30/)
  await expect(preview).toContainText('- **Class name:** IELTS B2 — Evening')
  await page.getByRole('button', { name: 'Record recurrence' }).click()

  // ── 4. The seeded report counts one more; no new report was created ────────
  await expect(page.getByText(/Recurrence recorded on BUG-/)).toBeVisible()
  // The form is cleared: the answers are gone and the panel went with them.
  await expect(page.getByTestId('recurrence-preview')).toBeHidden()
  await expect(modal.getByText('IELTS B2 — Evening')).toHaveCount(0)
  const after = await api(page, 'GET', `/issues/${seeded.id}`)
  expect(after.recurrence_count).toBe(seeded.recurrence_count + 1)
  await page.goto('/support/reports')
  await expect(page.getByRole('row', { name: new RegExp(title) })).toHaveCount(0)
  await supportCtx.close()
})
