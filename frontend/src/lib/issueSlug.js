// Builds and parses the `/issue/:slug` URL segment.
//
// New links use `bug-<n>` / `task-<n>` (03, docs/phase-2/03-tasks-and-placement.md).
// Old `issue-<n>` links (Telegram history, bookmarks) must keep resolving —
// `parseIssueSlug` accepts all three prefixes, `issueSlug` only ever emits
// the type-specific one.

const PREFIX_BY_TYPE = { bug: 'bug', task: 'task' }

export function issueSlug(issue) {
  const prefix = PREFIX_BY_TYPE[issue?.type] ?? 'issue'
  return `${prefix}-${issue.issue_number}`
}

const SLUG_RE = /^(?:bug|task|issue)-(\d+)$/

export function parseIssueSlug(slug) {
  const match = SLUG_RE.exec(slug ?? '')
  if (!match) return null
  return parseInt(match[1], 10)
}

// Display key for an issue-shaped object — `BUG-123` / `TASK-124` from the
// API's `key`, falling back to the legacy `issue-<n>` spelling for payloads
// that predate slice 03 (e.g. some report endpoints).
export function issueKey(issue) {
  if (issue?.key) return issue.key
  const prefix = PREFIX_BY_TYPE[issue?.type] ?? 'issue'
  return `${prefix}-${issue?.issue_number}`
}

// A typed reference to one item: `#13`, `13`, `BUG-13`, `bug-13`, `TASK-13`
// (a bare number or `#` matches either type; a prefix pins the type). Item
// numbers are global, so the number alone finds the item.
const REF_RE = /^(?:#|(bug|task|issue)-?)?(\d+)$/i

export function parseIssueRef(text) {
  const match = REF_RE.exec((text ?? '').trim())
  if (!match) return null
  const prefix = match[1]?.toLowerCase()
  return { number: parseInt(match[2], 10), type: prefix === 'bug' || prefix === 'task' ? prefix : null }
}
