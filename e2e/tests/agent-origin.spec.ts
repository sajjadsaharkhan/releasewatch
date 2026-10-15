import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Slice 17: an item filed through MCP carries the Agent badge on its page, and
// the backlog's Origin filter lists it. The agent here is a plain JSON-RPC call
// to /mcp with a personal MCP token — the way a coding agent reaches it.
// Seed: backend/scripts/seed_e2e.py.

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)
const SLUG = 'e2e-product'

test.use({ storageState: auth('admin') })

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
    return res.status === 204 ? null : res.json()
  }, { method, url, body })
}

/** One MCP tool call as a coding agent makes it; returns the structured result. */
async function mcpTool(page: Page, token: string, name: string, args: Record<string, unknown>) {
  return page.evaluate(async ({ token, name, args }) => {
    const res = await fetch('/mcp', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json, text/event-stream',
      },
      body: JSON.stringify({
        jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name, arguments: args },
      }),
    })
    const body = await res.json()
    if (!res.ok || body.error || body.result?.isError) {
      throw new Error(`${name} → ${res.status} ${JSON.stringify(body)}`)
    }
    return body.result.structuredContent
  }, { token, name, args })
}

test('An item filed through MCP shows the Agent badge, and the origin filter finds it', async ({ page }) => {
  await page.goto('/inbox')
  const stamp = Date.now()
  await api(page, 'PUT', '/settings/mcp', { enabled: true })
  const { value: token } = await api(page, 'POST', '/me/mcp/tokens', {
    name: `E2E agent ${stamp}`, lifetime_days: 30,
  })
  const agentTitle = `Agent debt check ${stamp} — retry loop`
  const filed = await mcpTool(page, token, 'rw_file_tech_debt', {
    project: SLUG, title: agentTitle, file_anyway: true,
  })
  expect(filed.via_agent).toBe(true)
  const projects = await api(page, 'GET', '/projects')
  const project = projects.find((p: { slug: string }) => p.slug === SLUG)
  const personTitle = `Person debt check ${stamp}`
  await api(page, 'POST', '/issues', {
    title: personTitle, type: 'task', project_id: project.id, is_tech_debt: true,
  })

  // The item page: the badge sits next to the owner's name.
  await page.goto(`/issue/${filed.key.toLowerCase()}`)
  const byline = page.getByText('Created by').locator('..')
  await expect(byline.getByText('Agent', { exact: true })).toBeVisible()

  // The backlog, technical debt shown, filtered to agent content.
  await page.goto(`/projects/${SLUG}/backlog?debt=1`)
  await expect(page.getByText(personTitle)).toBeVisible()
  await page.getByRole('button', { name: /Origin:/ }).click()
  await page.getByRole('button', { name: 'Agent', exact: true }).click()
  await expect(page).toHaveURL(/origin=agent/)
  await expect(page.getByText(agentTitle)).toBeVisible()
  await expect(page.getByText(personTitle)).toHaveCount(0)
})
