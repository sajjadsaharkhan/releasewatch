"""Retrieval constants (engine PRD Appendix A.8, BR-S19).

Fixed in code, never user settings. Each value names the evaluation run that
set it; a run that changes one updates its comment and checks its report into
``docs/phase-2/eval/``.
"""

#: Weighted reciprocal rank fusion, one weight per channel.
#: Set by: A.8 initial values — not yet tuned (no stage-1 run on the dataset).
FUSION_WEIGHTS = {"body": 1.0, "title": 0.6, "talk": 0.3, "keyword": 0.4}

#: RRF constant k. Set by: A.8 initial value.
RRF_K = 60

#: Results whose best dense cosine is below this are dropped when Jev is off
#: (FR-S04) — unless the gated keyword channel found them.
#: Set by: A.8 placeholder — tune on the stage-1 run.
T_FLOOR = 0.35

#: Trigram ``word_similarity(query, keyword_text)`` gate for the keyword
#: channel; ungated trigram ranks every Persian document (A.8).
#: Set by: A.8 placeholder — tune on the stage-1 run.
T_TRGM = 0.6

#: The keyword channel contributes at most this many items (A.8).
KEYWORD_TOP = 3

#: Each channel returns at most this many candidates before fusion (A.8).
CHANNEL_LIMIT = 50

#: Results hydrated after fusion, and returned when Jev is off (A.8).
HYDRATE_LIMIT = 30
RESULT_LIMIT = 20
PALETTE_LIMIT = 8

#: Query-vector cache lifetime, seconds (A.8 step 1).
QUERY_CACHE_TTL = 300
