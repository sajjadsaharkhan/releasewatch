# Rejected is a status; the cycle only records it

**Date:** 2026-09-30 · **Supersedes:** cycle-model.md CY-11 ("no Returned status, no extra column")

08a kept work that came back in **To do** and marked it with a returned marker computed from the
current cycle. That kept the status set small, but it put the most important fact about a work
item — "this was sent back" — behind a join: the board, filters, and anyone reading an item had
to ask the cycle table what the status didn't say. Sending work back also had three entry points
(a status move with a comment, a failing verification, and a separate return endpoint) and two
names (Reject, Return) for one act.

We decided that **Rejected is a status**, entered only by one **Reject** action with a comment,
from To review, In review, or Done. Cycles still record every pass and still classify where the
problem was caught (`review`, `release_qa`, `production`), because the Phase 3 reports need that
split (CY-09). But the cycle is now a ledger, not the source of what the UI shows. The reason is
an ordinary comment on the item.

We also added **To review** before In review, so that "the developer delivered it" and "QA is
checking it" are two states instead of one.

## Consequences

- Rejected cards live in the To do column with their own style; the board gains one column
  (To review), not two.
- Nothing enters Rejected through a plain status move. This is the one exception to the free
  workflow, and it exists because a Rejected status without a cycle and a comment would be a lie.
- A rejected item leaving the backlog path (moved to backlog, or its release ships) becomes To do,
  since its cycles are deleted.
- Once a developer picks rejected work up, the status no longer says it came back; a cycle badge
  (`↻ N`) does. That is deliberate: Rejected means "waiting for the developer", not "has history".
- Users see one action. Anyone tempted to split it back into Reject and Return should check the
  reports first: they already get the split from `start_reason`.

See [09a — To review, Rejected, and one Reject action](../phase-2/09a-review-queue-and-rejected.md).
