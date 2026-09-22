import { chromium, type FullConfig } from '@playwright/test'
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import { ROLES, PASSWORD } from './roles.js'

// package.json sets "type": "module", so there's no CommonJS __dirname here.
const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0]?.use?.baseURL ?? 'http://localhost:8082'
  const authDir = path.join(__dirname, '.auth')
  fs.mkdirSync(authDir, { recursive: true })

  const browser = await chromium.launch()
  try {
    for (const role of ROLES) {
      const page = await browser.newPage({ baseURL })
      await page.goto('/login')
      await page.getByLabel('Username').fill(`e2e-${role}`)
      await page.getByLabel('Password').fill(PASSWORD)
      // Keycloak's own button ("Sign in with Keycloak") also matches "Sign in"
      // under Playwright's default substring name matching — this env has
      // Keycloak configured, so it's rendered too. Disambiguate with exact.
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()
      await page.waitForURL('**/dashboard')
      await page.context().storageState({ path: path.join(authDir, `${role}.json`) })
      await page.close()
    }
  } finally {
    await browser.close()
  }
}
