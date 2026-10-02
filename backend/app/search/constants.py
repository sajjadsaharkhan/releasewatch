"""Retrieval constants (engine PRD Appendix A.8, BR-S19).

Fixed in code, never user settings. Each value names the evaluation run that
set it; a run that changes one updates its comment and checks its report into
``docs/phase-2/eval/``.
"""

#: Weighted reciprocal rank fusion, one weight per channel.
#: Set by: A.8 initial values — kept by the stage-1 run 2026-10-01 (Recall@5 0.833,
#: Q1 passed by +27 points); not tuned further.
FUSION_WEIGHTS = {"body": 1.0, "title": 0.6, "talk": 0.3, "keyword": 0.4}

#: RRF constant k. Set by: A.8 initial value.
RRF_K = 60

#: Results whose best dense cosine is below this are dropped when Jev is off
#: (FR-S04) — unless the gated keyword channel found them.
#: Set by: stage-1 run 2026-10-01 (docs/phase-2/eval/stage1-2026-10-01.md) — the
#: knee of the sweep: Recall@5 0.833 → 0.822, no-match results 20 → 11 per query,
#: 0.5 % of real queries left empty. bge-m3 cosines are high for unrelated text,
#: so no floor separates cleanly; Jev (slice 13) is what removes the rest.
T_FLOOR = 0.55

#: Trigram ``word_similarity(query, keyword_text)`` gate for the keyword
#: channel; ungated trigram ranks every Persian document (A.8).
#: Set by: A.8 value, kept by the stage-1 run 2026-10-01 (identifier queries R@5 0.774).
T_TRGM = 0.6

#: The keyword channel contributes at most this many items (A.8).
KEYWORD_TOP = 3

#: Each channel returns at most this many candidates before fusion (A.8).
CHANNEL_LIMIT = 50

#: Results hydrated after fusion, and returned when Jev is off (A.8).
HYDRATE_LIMIT = 30
RESULT_LIMIT = 20
PALETTE_LIMIT = 8

#: Jev rerank: candidates sent, and the relevance threshold that splits
#: ``results`` from ``less_relevant`` (FR-S03, A.8 step 6).
#: Set by: A.8 initial value (PoC demo: same-problem 0.91–0.94, related
#: 0.52–0.70, junk ≤ 0.44) — set the final value from the stage-2 run.
JEV_CANDIDATES = 15
T_RELEVANT = 0.5

#: Same-problem suggestions (slice 14, A.7 judge): candidates sent to Jev, and
#: the confidence a ``same`` / ``related`` verdict needs to be shown.
#: ``T_SAME`` is from the duplicate-dataset sweep of 2026-10-02
#: (docs/phase-2/eval/duplicate-threshold-2026-10-02.md, ``python -m
#: scripts.dup_dataset sweep``): the lowest value at which a shown hint is right
#: 92% of the time (precision 0.925, recall 0.805 on 148 drafts). Re-check it
#: with ``search_eval stage2 --part similar`` on real text.
#: ``T_RELATED`` is still the PoC ``bench_jev`` value, not swept.
SIMILAR_CANDIDATES = 10
T_SAME = 0.74
T_RELATED = 0.6
#: Suggestions returned to a form, and stored hints per New item (A.4/A.5).
SIMILAR_LIMIT = 5
DUPLICATE_HINT_LIMIT = 3

#: Query-vector cache lifetime, seconds (A.8 step 1).
QUERY_CACHE_TTL = 300
