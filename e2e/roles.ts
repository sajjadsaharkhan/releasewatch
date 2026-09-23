// Matches backend/scripts/seed_e2e.py — one known user per role, one shared
// password (docs/phase-2/01-test-harness.md). Shared between global-setup.ts
// and any spec that needs to name a role, so the two never drift apart.
export const ROLES = ['qa', 'developer', 'pm', 'cto', 'admin', 'support'] as const
// Everyone but Support (PRD §7.3) — the roles that get the dashboard.
export const TECH_ROLES = ROLES.filter((r) => r !== 'support')
export const PASSWORD = 'e2e-password-123'
