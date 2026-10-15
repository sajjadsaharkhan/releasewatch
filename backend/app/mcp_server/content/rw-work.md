# Work on {key}

Load the full context of the Releasewatch item {key} and prepare the work.

## Steps

1. Call `rw_get_item` with key `{key}`.
2. For each attachment that is an image, call `rw_get_attachment` and examine the image.
3. If the status of the item is `rejected`, start from the reject comment. Tell the developer why the item came back and what must change.
4. Give the developer a short summary of the task: the problem or the work, the evidence, the reproduction steps, the cURL command, the environment, and the open questions. Refer to other items by their key.
5. If the item is not In progress, tell the developer to move its status in Releasewatch. You do not change the status.
6. When the developer opens a PR, add one note with `rw_add_note` in the format of the standard (§5.4): `PR: [<PR title>](<url>)`, then one sentence about what the PR changes. Add one PR note for each PR. If a PR note of your agent has a wrong link, correct it with `rw_update_own`.
7. When you find new evidence about {key}, add a note: one sentence that states the finding, then an Evidence table. Do not change the description of an item you did not file.

The Agent Writing Standard follows this message. Use it for every note.
