# Releases get progress and risk, but never a schedule

A release holds the most consequential date this company owns, so the obvious move is to give it
everything a milestone gets — including sequencing, dependencies, and a Gantt. We decided not to.
A release gets **progress, confidence, and a risk signal against its ship date**, and nothing more.

The reason is that a release and a goal are judged differently. A release is judged on
**readiness**: is everything that must ship finished, and are the blockers clear? That question is
already answered by the go/no-go gate, which works and which stays. A goal is judged on
**delivery**, and delivery is where order, blocking, and a critical path actually mean something.
Giving a release a Gantt would invite planning the order of bug fixes, which nobody wants to
maintain and which would be stale within a day of a testing cycle starting.

## Consequences

- Sequencing is a goal-level activity, permanently. Work that needs ordering belongs to a milestone.
- The go/no-go decision remains the only gate on shipping. The risk signal informs it and never
  pre-empts or blocks it.
- The product named *Releasewatch* deliberately declines to schedule a release. Anyone encountering
  that and assuming it is an oversight is about to reverse this decision.

See [08 — Release progress & risk](../phase2/08-release-progress-and-risk.md).
