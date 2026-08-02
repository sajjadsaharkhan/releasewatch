const SEVERITY_EMOJI = {
  critical: '🔴',
  major: '🟠',
  minor: '🟡',
  trivial: '⚪',
}

function severityEmoji(severity, is_release_blocker) {
  if (severity === 'critical' || (severity === 'major' && is_release_blocker)) return '🔴'
  return SEVERITY_EMOJI[severity] ?? '⚪'
}

function redactCurl(curl) {
  return curl
    .replace(/(Authorization:\s*\S+\s*)\S+/gi, '$1<redacted>')
    .replace(/(Cookie:\s*)\S+/gi, '$1<redacted>')
    .replace(/(Bearer\s+)\S+/gi, '$1<redacted>')
}

export function buildIssueMarkdown(issue, comments = []) {
  const emoji = severityEmoji(issue.severity, issue.is_release_blocker)
  const lines = []

  // ── Title line ────────────────────────────────────────────────────────────
  lines.push(`# [${emoji}] ${issue.title}`)
  lines.push('')

  const meta = [
    `**Issue #${issue.issue_number}**`,
    issue.project_name && `Project: ${issue.project_name}`,
    issue.release_version && `Release: ${issue.release_version}`,
    `Status: \`${issue.status}\``,
    `Severity: \`${issue.severity}\``,
    issue.is_release_blocker && '🔴 Release Blocker',
    issue.is_regression && `⚠️ Regression (x${issue.regression_count})`,
  ].filter(Boolean).join(' · ')
  lines.push(meta)
  lines.push('')

  const labels = (issue.labels_detail || []).map(l => l.name).join(', ')
  if (labels) lines.push(`**Labels:** ${labels}`)
  if (issue.parent_issue_id) lines.push(`**Parent Issue:** #${issue.parent_issue_id}`)
  if (labels || issue.parent_issue_id) lines.push('')

  // ── Description ──────────────────────────────────────────────────────────
  lines.push('## Description')
  lines.push(issue.description?.trim() || '_No description provided._')
  lines.push('')

  // ── Reproduction Steps ───────────────────────────────────────────────────
  lines.push('## Reproduction Steps')
  const steps = issue.reproduction_steps || []
  if (steps.length === 0) {
    lines.push('_No structured repro steps provided — consider requesting numbered steps from reporter._')
  } else {
    for (const s of steps) {
      lines.push(`${s.step_order}. ${s.description}`)
      if (s.expected_result) lines.push(`   - Expected: ${s.expected_result}`)
      if (s.actual_result) lines.push(`   - Actual: ${s.actual_result}`)
    }
  }
  lines.push('')


  // ── Repro Request ─────────────────────────────────────────────────────────
  if (issue.curl_command?.trim()) {
    lines.push('## Repro Request')
    lines.push('```bash')
    lines.push(redactCurl(issue.curl_command.trim()))
    lines.push('```')
    lines.push('*(sensitive headers redacted)*')
    lines.push('')
  }

  // ── Comments ──────────────────────────────────────────────────────────────
  if (comments.length > 0) {
    lines.push('## Comments')
    lines.push('')
    for (const c of comments) {
      const author = c.actor_user?.name ?? 'Unknown'
      const internal = c.isInternal ? ' _(internal)_' : ''
      lines.push(`**${author}**${internal}:`)
      lines.push('')
      lines.push(c.body?.trim() ?? '')
      lines.push('')
      lines.push('---')
      lines.push('')
    }
  }

  return lines.join('\n')
}

export function downloadIssueMarkdown(issue, comments = []) {
  const md = buildIssueMarkdown(issue, comments)
  const blob = new Blob([md], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `issue-${issue.issue_number}.md`
  a.click()
  URL.revokeObjectURL(url)
}
