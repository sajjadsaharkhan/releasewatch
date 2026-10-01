"""Search engine evaluation harness (slice 12 ``stage1``; 13 adds ``stage2`` and
``comments``). See ``python -m scripts.search_eval --help``.

Reads the dataset built per ``docs/phase-2/search-eval-dataset-spec.md`` and
scores the engine with its **own** code — ``app.search.documents`` builds the
documents, ``app.search.comment_rules`` decides which comments are talk, and
``app.search.retrieval`` fuses and floors — against an in-memory dense index
plus a temporary Postgres table for the trigram channel. Ported in spirit from
the PoC's ``bench_embed.py``.
"""
