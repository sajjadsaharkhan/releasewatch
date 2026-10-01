# Spec: Build the Releasewatch search & duplicate-detection evaluation dataset

**Audience:** an agent with read access to the Releasewatch PostgreSQL database.
**Output:** labelled JSON files that the evaluation harness loads (`backend/scripts/search_eval/`, see
[prd-search-engine.md](prd-search-engine.md) §8 and Appendix A.13; the PoC in `poc/semantic-search/`
reads the same shape).
**Why:** Releasewatch has no record of real duplicates or real search queries yet. We need
ground truth ("which issue is the right answer?") to measure the search engine and the
similar-issue / duplicate / regression suggestions before we ship them.

The dataset is **synthetic queries and drafts written about real issues**. The corpus
being searched is the real issue table.

---

## 1. Hard rules

1. **Read-only.** Connect to a read-only replica or a restored snapshot, never the primary.
   Run `SELECT` only. No writes, no temp tables in the source DB, no `LISTEN`.
2. **No circular labelling.** Do not use Releasewatch's own search, `issue_embeddings`, pgvector,
   or any embedding model to decide relevance labels. Find candidates with plain SQL
   (`ILIKE`, `pg_trgm` `similarity()`, filtering by project/label) and **read them**. A label
   produced by the system under test cannot evaluate that system.
3. **Mask personal data** in everything you write out. Replace with a typed placeholder:
   - Iranian mobile numbers (`09\d{9}`, `\+989\d{9}`) → `<PHONE>`
   - 10-digit national IDs → `<NATIONAL_ID>`
   - emails → `<EMAIL>`
   - card/IBAN numbers (16 digits, `IR\d{24}`) → `<CARD>`
   - tokens, cookies and `Authorization` headers inside `curl_command` → `<SECRET>`
   - person names of customers or students, when clearly present → `<PERSON>`. Leave staff
     usernames alone.

   Apply the same masking to the corpus export and to anything you generate.
4. **Exclude** soft-deleted rows (`deleted_at IS NOT NULL`) everywhere.
5. Record the snapshot timestamp and a random seed in the manifest, so the sampling can be
   reproduced.

---

## 2. Corpus export (the search space)

Export **all** non-deleted issues, not only the sampled ones. Search quality depends on
corpus size, so a 60-issue toy corpus overstates quality.

`corpus/issues.json`: a list of:
```json
{
  "id": "147",                      // issues.id as string
  "issue_number": 156,
  "project_id": 2,
  "project_name": "Chat",
  "release_id": 3,                  // null if none
  "status": "verified",             // as stored in the snapshot (Phase 1 or Phase 2 values)
  "severity": "enhancement",
  "labels": ["chat"],
  "reporter_role": "developer",     // qa|developer|cto|admin (from users.role)
  "title": "Connecting Status (Telegram-Style)",
  "description": "...masked...",
  "reproduction_steps": [{"description": "...", "expected_result": "...", "actual_result": "..."}],
  "curl_path": "/api/v1/chat/conversations",   // URL path only from curl_command, no host/headers/body
  "created_at": "2026-07-14T07:29:11Z"
}
```

`corpus/comments.json`: all `issue_timeline` rows with `event_type = 'comment'` and a
non-empty body:
```json
{"id": "930", "issue_id": "147", "author_role": "cto", "is_internal": false,
 "body": "...masked...", "created_at": "..."}
```

---

## 3. Sampling the base issues

Pick **150 base issues** (fewer only if the corpus is smaller), stratified by:
- project, proportional, with a minimum of 5 per project
- status, with at least 30% Done (Phase 1: `verified`/`closed`), needed for regression cases
- severity, including `enhancement` (feature requests behave differently from bugs)
- language of title+description: Persian / English / mixed. Keep the natural ratio,
  with at least 20 of each where they exist.
- length: at least 20 issues with a description over 150 words and at least 20 with a
  very short or empty description

Skip issues whose title and description together are under ~8 meaningful words. They
cannot anchor a meaningful query.

---

## 4. What to generate

### 4.1 Search queries → `queries.json`

For each base issue write **2 or 3 queries** that a Releasewatch user would type to find it.
Each query uses a **different style** from this list, and gets tagged with it in `cat`:

| tag | style | example (for a "reactions not saved in group chat" issue) |
|---|---|---|
| `short` | 1–3 words | `ری‌اکشن گروه` |
| `colloquial` | spoken Persian | `ری اکشنا تو گروه نمیمونه` |
| `codeswitch` | Persian sentence with English tech words | `مشکل reaction در group chat` |
| `translit` | English loanwords written in Persian script | `ریاکشن تو چت گروهی ثبت نمیشه` |
| `typo` | 1–2 realistic typos or missing ZWNJ | `عدم ثب ری اکشن در چت گروه` |
| `fa2en` | Persian query, English issue | |
| `en2fa` | English query, Persian issue | `reaction not saved in group` |
| `symptom` | describes what the user saw, avoiding the issue's key terms | `بعد رفرش ایموجی‌هایی که زدیم پاک میشن` |
| `identifier` | error code / endpoint / screen name taken from the issue | `/api/v1/chat/reactions 500` |

Rules:
- **No copy-paste.** A query must not share 4 or more consecutive words with the issue's
  title or description. The validation script checks this.
- Add `cross_lingual` whenever the query language differs from the issue's main language,
  in addition to the style tag.

**Relevance labels (the most important part).** For every query, search the corpus with
SQL and by reading, and label **every** issue that answers it:
- `2`: the user is looking for this issue (same problem)
- `1`: related: same feature or area, but a different problem
- unlisted = irrelevant

A query often has several grade-2 answers (two reports of the same bug). A missing
grade-2 label makes a correct result count as an error, so look for them deliberately:
same project, same feature words in both languages, same error code.

Also write **25 no-match queries**: plausible for these projects, but answered by no issue.
Some should reuse vocabulary from real issues about a different problem, e.g.
`ری‌اکشن روی کامنت تکلیف` when only chat reactions exist.

```json
{"queries": [
  {"id": "q001", "q": "مشکل reaction در group chat", "cat": ["codeswitch", "cross_lingual"],
   "base_issue": "147", "rel": {"147": 2, "152": 2, "160": 1}}
 ],
 "no_match": [{"id": "x001", "q": "..."}]}
```

### 4.2 New-issue drafts → `drafts.json`

These simulate someone writing a new report in the create form (tech team) or the support
form, and measure similar-issue suggestions, triage merge hints, and regression detection.

Generate 4 kinds:

| kind | count | how | gold |
|---|---|---|---|
| `duplicate` | ~120 | Rewrite a base issue as a **fresh report** by a different person (see personas). Different words, different detail level, possibly different language. | `same` = [base + any other issue that is truly the same problem] |
| `recurrence` | ~40 | Only for Done bases (Phase 1: `verified`/`closed`). Report the same problem as happening again ("after the last update this is back…"). | `same` = [base] |
| `hard_negative` | ~60 | Same project and feature as a base issue, **different faulty behaviour** (same screen, different bug; same feature, different platform or condition). | `same` = [], `related` = [base, …] |
| `novel` | ~30 | A plausible new problem for the project that no issue describes. | `same` = [], `related` = […] if any |

Personas (tag with `persona`):
- `support`: customer-facing, colloquial Persian, little technical detail, often mentions a
  customer or institute (masked), may follow a template ("شرح مشکل: … / مراحل: …")
- `qa`: structured, steps, expected vs actual, environment
- `developer`: terse, technical, may be English or code-switched, may cite endpoints or errors

Rules:
- Titles are short, the way people really write them. Descriptions range from empty to a
  full paragraph. Vary this.
- Label `same` and `related` against the **whole corpus**, not just the base, using the same
  search-and-read process as 4.1.
- Do not include cancelled issues in `same` (they are excluded from suggestions by design).

```json
{"drafts": [
  {"id": "n001", "kind": "duplicate", "persona": "support", "project_id": 2,
   "title": "ری‌اکشن‌ها بعد رفرش میپرن", "description": "...",
   "base_issue": "147", "same": ["147"], "related": ["160"],
   "cat": ["colloquial", "cross_lingual"]}
]}
```

The benchmark derives the expected action from the matched issue's status, so you do not
write it. For reference (PRD v3 BR-49): Done (Phase 1: `verified`/`closed`) → back to To do
with a new cycle (release QA or production); Cancelled → stays cancelled; any other status →
merge without a status change. Matched issues may be bugs or tasks.

### 4.3 Comment labels → `comments_labelled.json`

Sample **150 real comments** from `corpus/comments.json`, stratified: mix of short and long,
internal and non-internal, and from issues that have 3 or more comments. Label each one
**in the context of its issue's title and description**:

| label | meaning |
|---|---|
| `this_problem` | adds technical detail about this issue: symptom, cause, reproduction, scope, error, fix |
| `other_problem` | mainly about a different problem or another project |
| `process` | coordination, planning, assignment, product or priority decisions; no technical content |
| `ack` | agreement, thanks, acknowledgement, status ping |

```json
{"id": "930", "issue_id": "147", "label": "other_problem",
 "rationale": "discusses token refresh fixed in the Student project, not the connecting-status feature"}
```

---

## 5. Label quality

1. **Two passes.** Generate everything in pass 1. In pass 2, re-check every label **in a
   fresh context** without the pass-1 reasoning: re-read the query or draft and the labelled
   issues, and search again for missed grade-2 answers.
2. If the passes disagree, keep the pass-2 label and add `"needs_review": true` plus a
   one-line `"review_note"`.
3. Write a random 10% sample (seeded) to `review_sample.json` for human spot-checking.

---

## 6. Validation (write and run `validate_dataset.py`)

Fail the run if any of these fail:
- every id in `rel`, `same`, `related`, `base_issue` exists in the corpus
- every query has at least one grade-2 label, except `no_match`
- every draft of kind `duplicate`/`recurrence` has a non-empty `same`; every
  `hard_negative`/`novel` has an empty `same`
- no query or draft shares 4 or more consecutive tokens with its base issue's title or
  description (after normalizing Arabic/Persian letters and ZWNJ)
- no unmasked phone, email, national ID or card pattern anywhere in the output
- category and persona tags are from the lists above

Print the distribution (counts per project, cat, persona, kind, language, label) into
`MANIFEST.md`.

---

## 7. Deliverable layout

```
eval-dataset/
  MANIFEST.md                 # snapshot time, seed, counts, distributions, known gaps
  corpus/issues.json
  corpus/comments.json
  queries.json
  drafts.json
  comments_labelled.json
  review_sample.json
  validate_dataset.py
```

## 8. Out of scope

- Do not run the search engine, embedding models or Jev. Evaluation is a separate step.
- Do not modify anything in the database.
- Do not invent issues in the corpus. Synthetic text appears only in queries and drafts.
