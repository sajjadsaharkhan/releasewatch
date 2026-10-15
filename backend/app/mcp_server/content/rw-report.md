# Report a problem to Releasewatch

Help the developer report a problem as a bug or as technical debt. The Agent Writing Standard follows this message. Read it before you write.

## Steps

1. Gather the evidence. Use the codebase, this conversation, and the tools the developer has: Sentry, Kibana or Elasticsearch, Grafana, CI, a database query, a local run. For each source, write down the source, an exact locator, and the time range with a time zone. Give a link only when you opened it or the developer gave it. When you cannot open a source, write "Not verified".
2. Decide with the developer if this is a **bug** (the product does not behave as it must) or **technical debt** (the code works, but its state causes risk or cost). For technical debt, call `rw_tech_debt` and look for an item that already records it.
3. Call `rw_context` to get the project key, if you do not know it.
4. Write the draft by the template of the item type (§5): the title, the required sections, and the Evidence table. For a bug, put the reproduction steps, the cURL command, and the environment in their fields, not in the description. Write one action in each step, and put each precondition (the user to sign in as, the data) in its own step. Do not write the environment in a step. Mark each guess with **Hypothesis:**. Do the self-check (§8).
5. Find the attachments the standard requires (§7): a screenshot or a recording, a log, a script, a query or a result set of more than 20 lines, or a trace, HAR, or dump file. Name each file `<source>-<content>-<yyyymmdd>.<ext>` and refer to it by name in the description.
6. For technical debt, propose a priority and tell the developer why. Use it only if the developer confirms it. If not, the priority is Medium.
7. Show the developer the complete draft, the attachments, and the priority. Do not file before the developer agrees. Change the draft as the developer asks.
8. Upload each attachment: call `rw_upload_prepare`, then upload the file with your shell to the URL it returns.
9. File the item with `rw_file_bug` or `rw_file_tech_debt`, with the `upload_ids`. Do not set `file_anyway`.
10. If the result is `duplicates_found`, read each candidate with `rw_get_item`. Tell the developer which candidates describe the same problem, and ask:
    - **File anyway:** file again with `file_anyway=true`.
    - **Document the existing item:** add a note with the new evidence (`rw_add_note`), attach the files (`rw_attach`), fill empty fields (`rw_fill_field`), and, if the developer confirms that the problem occurred again, report a recurrence (`rw_report_recurrence`).
    - If the same problem is in a **Done** item, file a new bug and name the Done item under "Related items". A recurrence is not possible on a Done item.
11. Give the developer the key and the link of the item.
