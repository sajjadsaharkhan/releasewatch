# Effort is optional, and analyses exclude rather than estimate

Releasewatch 2.0 needs to forecast goals and releases, and every comparable tool solves that by
requiring an estimate on every work item. We decided the opposite: estimate, remaining, and actual
are optional everywhere, and any analysis that needs them — Gantt, critical path, projected finish,
schedule risk — **excludes work that lacks them and states loudly how much it excluded**, rather
than filling the gap with an average, a historical guess, or a default.

The reason is that this team does not work one way. Some goals carry a committed external date and
deserve the planning investment; most do not and never will. Requiring estimates everywhere would
tax all work to serve a minority of it, and the numbers collected under that tax would be entered
without care and then trusted as though they had been.

## Consequences

- A milestone can only be planned in time once someone deliberately sizes its work. Few will be, and
  that is intended.
- Every projected number carries a caveat naming what it left out. A date is never displayed naked.
- Progress is counted in **items** by default, not hours, because hours are unavailable for most
  work.
- Anyone later tempted to "fix" a partial forecast by defaulting unestimated work to an average is
  reversing this decision. A number that looks real but is invented is the specific failure mode
  [Test 6.6](../phase2-problem-statement.md#6-what-solved-looks-like) exists to prevent — it will be
  trusted, and it should not be.

See [09 — Effort](../phase2/09-effort.md) and
[10 — Time-based planning](../phase2/10-time-based-planning.md).
