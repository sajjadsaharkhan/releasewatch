# Stage-2 evaluation (similar) — 2026-10-02

Dataset `/tmp/eval-dataset`: 252 drafts (duplicate 120, recurrence 42, hard_negative 60, novel 30). Candidates: body+title stage 1, top 10, not Cancelled; Jev judge, top 3 `same` shown. Jev failures: {'network': 12}.

The snapshot is Phase 1 data (no support-sourced items), so this runs the triage filter; the support panel's open-support filter has nothing to filter.

## Gates — Q3: same-problem precision on duplicate + hard-negative ≥ 0.80

At `T_SAME = 0.74`: **0.930** — pass

## In effect now (T_SAME = 0.74)

| kind | shown | precision | recall | F1 |
|---|---|---|---|---|
| duplicate | 142 | 0.930 | 0.835 | 0.880 |
| recurrence | 43 | 0.930 | 0.755 | 0.833 |
| hard_negative | 0 | 0.000 | 0.000 | 0.000 |
| novel | 0 | 0.000 | 0.000 | 0.000 |

## Reference: stage-1 top-3 without Jev

| kind | shown | precision | recall | F1 |
|---|---|---|---|---|
| duplicate | 360 | 0.339 | 0.772 | 0.471 |
| recurrence | 126 | 0.310 | 0.736 | 0.436 |
| hard_negative | 180 | 0.000 | 0.000 | 0.000 |
| novel | 90 | 0.000 | 0.000 | 0.000 |

## T_SAME sweep

| T | duplicate P/R/F1 | recurrence P/R/F1 | hard_negative P/R/F1 | novel P/R/F1 |
|---|---|---|---|---|
| 0.20 | 0.792 / 0.867 / 0.828 | 0.778 / 0.792 / 0.785 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.25 | 0.792 / 0.867 / 0.828 | 0.778 / 0.792 / 0.785 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.30 | 0.797 / 0.867 / 0.830 | 0.792 / 0.792 / 0.792 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.35 | 0.815 / 0.867 / 0.840 | 0.840 / 0.792 / 0.816 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.40 | 0.825 / 0.867 / 0.846 | 0.875 / 0.792 / 0.832 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.45 | 0.825 / 0.867 / 0.846 | 0.891 / 0.774 / 0.828 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.50 | 0.834 / 0.861 / 0.847 | 0.932 / 0.774 / 0.845 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.55 | 0.865 / 0.854 / 0.860 | 0.932 / 0.774 / 0.845 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.60 | 0.888 / 0.854 / 0.871 | 0.932 / 0.774 / 0.845 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.65 | 0.893 / 0.848 / 0.870 | 0.932 / 0.774 / 0.845 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.70 | 0.918 / 0.848 / 0.882 | 0.932 / 0.774 / 0.845 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.75 | 0.930 / 0.835 / 0.880 | 0.930 / 0.755 / 0.833 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.80 | 0.942 / 0.829 / 0.882 | 0.930 / 0.755 / 0.833 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.85 | 0.942 / 0.816 / 0.875 | 0.929 / 0.736 / 0.821 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.90 | 0.954 / 0.785 / 0.861 | 0.975 / 0.736 / 0.839 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000
| 0.95 | 0.968 / 0.759 / 0.851 | 1.000 / 0.679 / 0.809 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000

## Recommendation

**Keep `T_SAME = 0.74`.** The Q3 gate passes with room (0.930 against 0.80), and it agrees with the synthetic-dataset sweep (`duplicate-threshold-2026-10-02.md`), which picked the same value from different data.

- **It sits on the plateau.** Duplicate precision climbs from 0.918 (0.70) to 0.930 (0.75) to 0.942 (0.80) while recall slips 0.848 → 0.835 → 0.829; F1 is flat at about 0.88 from 0.70 to 0.80. Anywhere in 0.70–0.80 is defensible; 0.74 is the lowest value that reaches 0.93 precision. Below 0.60 precision falls away (0.79–0.83) with no recall gain.
- **No false hints on the hard cases.** At 0.74, hard-negative and novel drafts get **zero** hints (the stage-1 reference shows 180 and 90 shown without Jev). Their P/R/F1 rows read 0 only because they have no same-problem gold items.
- **Recurrence recall is lower** (0.755 against 0.835): re-reports are phrased more differently from their originals. Raising the threshold would cost it more than it gains.
- **Caveats.** 12 of 252 drafts (4.8%) failed with a Jev network error and count as "no hint", which lowers recall slightly. The snapshot is Phase 1 data with no support-sourced items, so the support panel's filter was not exercised. This report evaluates `T_SAME` only; `T_RELATED` (0.6) is still the PoC value.
- **Re-run before changing the Jev model.** Thresholds are tied to `jev-1.13.0`.
