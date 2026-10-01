# Duplicate-detection dataset (synthetic, importable)

A **fake but realistic** set of issues for trying the Phase 2 similar-item / duplicate
engine in a development environment: 176 issues in the five projects Releasewatch is
used for (Chat, Limsa, Dano, StudentPanel, Releasewatch), 70 comments, 148 new-report
drafts and 139 search queries (+22 that nothing answers), all with gold labels.

Nothing here comes from production. The wording imitates the real tracker (Persian, English
and code-switched text; support, QA and developer voices; vague and detailed reports).

## What is in it

| Piece | What it tests |
|---|---|
| **Duplicate clusters** (60) | An original plus 1–3 re-reports in other words/languages, from other roles. Some originals are **Done** (so a recurrence merges back to *To do*), some are open; some re-reports are already **New** in triage; four are **Cancelled** duplicates that must never be suggested. |
| **Hard negatives** | Same project + feature, a different faulty behaviour (`rel_clusters` link sibling clusters). Must not be called *Same problem*. |
| **Background issues** (50) | Unrelated issues — noise so the corpus is not a toy. |
| **Drafts** | `duplicate` 73 · `recurrence` 23 · `hard_negative` 30 · `novel` 22, each with persona, difficulty and `signal_fields` (which part of the issue carries the match). |
| **Queries** | Short, colloquial, code-switch, transliterated, typo, symptom, identifier, cross-lingual; plus 22 no-match. |

**Which fields are used where.** The engine judges *same problem* on **title + description +
reproduction steps** only (engine PRD principle S4); cURL paths and labels feed the keyword
channel; **comments** feed search (`talk`) but never duplicate detection. So every issue carries
repro steps / a cURL path / comments where real ones would, and a few clusters are built so
that **only a comment** names the real fault (`signal_fields: ["comments"]`) — a duplicate miss
there is expected, a *search* miss is not. Use `signal_fields` to see which field a failure
depends on.

## Run it

```sh
make dup-dataset-import        # users, projects, issues, comments, search index, hints
make dup-dataset-probe         # drives GET /search and POST /search/similar, writes probe_report.md
```

or, without `make`:

```sh
docker compose exec api python -m scripts.dup_dataset import [--wipe] [--no-index] [--password …]
docker compose exec api python -m scripts.dup_dataset probe  [--k 5]
docker compose exec api python -m scripts.dup_dataset guide  # rewrite scenarios.md
```

`import` creates users `dd-qa`, `dd-developer`, `dd-pm`, `dd-support`, `dd-cto`, `dd-admin`
(password `dataset-pass-123`) and projects `dd-chat`, `dd-limsa`, `dd-dano`, `dd-studentpanel`,
`dd-releasewatch`. It is additive and refuses to run twice; `--wipe` deletes the earlier `dd-*`
projects first. It then indexes every issue for search through the configured embedding endpoint
(real `bge-m3` in dev) and, when Jev is on, computes triage hints for the New bugs.

Dates are shifted so the newest issue is an hour old. Everything is marked with the label
`dataset-dup`.

After `import`, open **`fixtures/dataset/scenarios.md`**: a hand-test script with the exact text
to type, who to sign in as, and which issue keys (from *your* database) should appear.

The probe needs a reachable API (`--base-url`, default `http://localhost:8000`). With Jev off it
reports stage-1 only; with Jev on it also scores the *same problem* judgement per draft kind.

## Files

```
fixtures/clusters/*.json   the authored source (edit these)
fixtures/patches.json      extra drafts/queries appended to clusters
fixtures/no_match.json     queries nothing answers
fixtures/dataset/          generated — committed so `import` needs no build
  corpus/issues.json  corpus/comments.json  drafts.json  queries.json  gold.json  MANIFEST.md
  (import_map.json, scenarios.md, probe_report.md are generated per database and git-ignored)
```

`corpus/`, `queries.json` and `drafts.json` keep the shape of `search-eval-dataset-spec.md`
(+ `type`, `source`, `cluster_id`, `duplicate_of`, `signal_fields`, `difficulty`), so
`backend/scripts/search_eval` can load the directory with `--dataset`.

Edit a cluster, then:

```sh
python -m scripts.dup_dataset build
python -m scripts.dup_dataset validate --manifest
```

`validate` enforces the spec's rules (ids exist, a grade-2 label per query, `same` empty for
hard negatives and novel drafts, recurrences point at a Done issue, no cancelled issue in `same`,
no 4-token copy of the base text, no phone/email/ID patterns). A test
(`tests/test_dup_dataset.py`) fails if the committed dataset drifts from the clusters.

## Honest limits

- It is fake: written by a model, then validated mechanically. Labels follow the authored
  cluster structure; they were not re-labelled by a second independent pass.
- A real run with `bge-m3` (and Jev) is what measures quality. Against the CI fake embedder
  (character trigrams) only lexical matches are found — the probe works, the numbers mean nothing.
- Some labels are debatable at the edges (`related` vs unrelated); gold `same` is the part to trust.
