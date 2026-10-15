# Start the next Releasewatch item

Load the developer's next item from Releasewatch, the team's QA tracker, and prepare the work.

## Steps

1. Call `rw_my_queue`.
2. Select the item. Use the first entry in the group `in_progress`. If no entry is In progress, use the first entry of the queue. If the queue is empty, tell the developer and stop.
3. Call `rw_get_item` with the key of the item.
4. For each attachment that is an image, call `rw_get_attachment` and examine the image.
5. If the status of the item is `rejected`, start from the reject comment. Tell the developer why the item came back and what must change.
6. Give the developer a short summary of the task: the problem or the work, the evidence, the reproduction steps, the cURL command, the environment, and the open questions. Refer to other items by their key.
7. Tell the developer to move the status of the item in Releasewatch, for example to In progress. You do not change the status.

When the developer opens a PR for this item, add one note with `rw_add_note` in this format: `PR: [<PR title>](<url>)`, then one sentence about what the PR changes.
