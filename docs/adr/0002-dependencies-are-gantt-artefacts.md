# Dependencies are Gantt artefacts, not work-item properties

Most issue trackers put `blocks` and `blocked by` on the work item itself, so anyone can assert a
dependency at any time from anywhere. We decided that in Releasewatch a dependency is a **planning
statement**: it exists only inside a milestone that has been planned in time, it is authored and
maintained on the Gantt, and a work item carries no dependency fields of its own.

The reason is that a dependency here has exactly one job — determining schedule order — and a link
asserted casually outside that context would carry no schedule effect while looking as though it
did. Keeping them in the one place they mean something also keeps the graph small enough to stay
correct, and puts the cost of maintaining it on the person who benefits from it.

## Consequences

- Adding work to a milestone that is already planned sends the owner back to the chart to place it.
  New work arrives unplaced and visibly so.
- A person's own screen never shows "blocked by X". Blocking that people need to see day to day is
  expressed as the **Blocked** status with a required reason, which is visible everywhere.
- A milestone whose owner stops maintaining the chart shows a schedule describing a plan that no
  longer exists. This is a real cost and is mitigated only by making unplaced work visible.
- Anyone later adding `blocks` / `blocked by` fields to a work item is reversing this decision.

See [11 — Gantt & dependencies](../phase2/11-gantt-and-dependencies.md).
