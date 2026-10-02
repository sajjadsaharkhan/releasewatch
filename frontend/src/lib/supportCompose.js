// Compose a support report's markdown exactly as backend/app/support_report.py
// `compose_report` (slice 05) will when the report is submitted. The recurrence
// flow (slice 14, FR-S10) adds the composed content to an existing item instead
// of filing a new report, so the confirmation shows the very text that will be
// recorded — this port keeps the preview and the submission in step.
//
// Only the rendering half is needed here: the form's own validation
// (TemplateFields.checkFieldValue + the modal's validate) has already passed by
// the time we compose.

const MD_SPECIAL = /([\\`*_\[\]()~@<>#|!])/g

export const escapeMd = (text) => String(text).replace(MD_SPECIAL, '\\$1')

const isBlank = (v) => v == null || (typeof v === 'string' && v.trim() === '')

function renderValue(field, raw) {
  switch (field.field_type) {
    case 'short_text': {
      const text = raw.trim().split(/\s+/).join(' ')
      return escapeMd(text)
    }
    case 'long_text':
      return null // rendered line by line by the caller
    case 'number':
      return String(Number(raw))
    case 'date':
      return String(raw).slice(0, 10)
    case 'datetime':
      return String(raw).slice(0, 16).replace('T', ' ')
    case 'single_select': {
      const opt = (field.options ?? []).find((o) => String(o.value) === String(raw))
      return escapeMd(String(opt?.label ?? opt?.value ?? raw))
    }
    case 'url':
      return escapeMd(String(raw).trim())
    default:
      return escapeMd(String(raw))
  }
}

/** The report markdown: `**Report template:** …`, `- **Label:** value`
 *  bullets (long text as `>` quote lines), `---`, then the free text. */
export function composeReport(template, values, freeText) {
  const lines = []
  for (const f of template.fields ?? []) {
    const raw = values?.[f.id]
    if (isBlank(raw)) continue
    const label = escapeMd(f.label)
    if (f.field_type === 'long_text') {
      const body = String(raw).split('\n').filter((l) => l.trim())
      if (!body.length) continue
      lines.push(`- **${label}:**`)
      for (const line of body) lines.push(`> ${escapeMd(line)}`)
    } else {
      lines.push(`- **${label}:** ${renderValue(f, raw)}`)
    }
  }
  const parts = [`**Report template:** ${escapeMd(template.name)}`]
  if (lines.length) parts.push(lines.join('\n'))
  const description = (freeText ?? '').trim()
  if (description) {
    parts.push('---')
    parts.push(description)
  }
  return parts.join('\n\n')
}
