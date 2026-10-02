# Duplicate-hint threshold sweep — 2026-10-02

**Recommendation: `T_SAME = 0.74`** — the lowest threshold at which a shown hint is right at least 92% of the time (precision 0.925, recall 0.805; 93% of duplicate/recurrence drafts get a correct hint, 8% of hard-negative and novel drafts get a wrong one).

Source: the synthetic duplicate dataset (148 drafts, 1480 Jev judgments, judged 2026-10-02); Jev failures: none. A hint is a `same` verdict at or above the threshold, at most 3 per draft, candidates as for a triage hint (same project, bugs and tasks, not Cancelled). Re-check against real text with `search_eval stage2 --part similar` before trusting the last decimal.

| T_SAME | precision | recall | F1 | correct hint on dup/recurrence drafts | wrong hint on hard-neg/novel drafts | TP | FP | FN |
|---|---|---|---|---|---|---|---|---|
| 0.50 | 0.899 | 0.870 | 0.884 | 95.8% | 9.6% | 134 | 15 | 20 |
| 0.52 | 0.905 | 0.870 | 0.887 | 95.8% | 9.6% | 134 | 14 | 20 |
| 0.54 | 0.905 | 0.870 | 0.887 | 95.8% | 9.6% | 134 | 14 | 20 |
| 0.56 | 0.905 | 0.864 | 0.884 | 95.8% | 9.6% | 133 | 14 | 21 |
| 0.58 | 0.904 | 0.857 | 0.880 | 95.8% | 9.6% | 132 | 14 | 22 |
| 0.60 | 0.904 | 0.857 | 0.880 | 95.8% | 9.6% | 132 | 14 | 22 |
| 0.62 | 0.910 | 0.857 | 0.883 | 95.8% | 9.6% | 132 | 13 | 22 |
| 0.64 | 0.910 | 0.857 | 0.883 | 95.8% | 9.6% | 132 | 13 | 22 |
| 0.66 | 0.910 | 0.851 | 0.879 | 94.8% | 9.6% | 131 | 13 | 23 |
| 0.68 | 0.908 | 0.831 | 0.868 | 93.8% | 9.6% | 128 | 13 | 26 |
| 0.70 | 0.914 | 0.825 | 0.867 | 93.8% | 7.7% | 127 | 12 | 27 |
| 0.72 | 0.913 | 0.818 | 0.863 | 92.7% | 7.7% | 126 | 12 | 28 |
| 0.74 **←** | 0.925 | 0.805 | 0.861 | 92.7% | 7.7% | 124 | 10 | 30 |
| 0.76 | 0.931 | 0.792 | 0.856 | 91.7% | 7.7% | 122 | 9 | 32 |
| 0.78 | 0.938 | 0.779 | 0.851 | 90.6% | 7.7% | 120 | 8 | 34 |
| 0.80 | 0.944 | 0.773 | 0.850 | 89.6% | 7.7% | 119 | 7 | 35 |
| 0.82 | 0.943 | 0.753 | 0.838 | 87.5% | 7.7% | 116 | 7 | 38 |
| 0.84 | 0.942 | 0.740 | 0.829 | 85.4% | 7.7% | 114 | 7 | 40 |
| 0.86 | 0.941 | 0.727 | 0.821 | 83.3% | 7.7% | 112 | 7 | 42 |
| 0.88 | 0.940 | 0.708 | 0.807 | 83.3% | 7.7% | 109 | 7 | 45 |
| 0.90 | 0.938 | 0.682 | 0.789 | 82.3% | 7.7% | 105 | 7 | 49 |
| 0.92 | 0.935 | 0.649 | 0.766 | 78.1% | 7.7% | 100 | 7 | 54 |
| 0.94 | 0.941 | 0.617 | 0.745 | 77.1% | 5.8% | 95 | 6 | 59 |
| 0.96 | 0.966 | 0.545 | 0.697 | 67.7% | 5.8% | 84 | 3 | 70 |
| 0.98 | 0.955 | 0.416 | 0.579 | 51.0% | 5.8% | 64 | 3 | 90 |
| 1.00 | 0.947 | 0.117 | 0.208 | 14.6% | 1.9% | 18 | 1 | 136 |

## Drafts that get at least one hint, by kind (at the recommended threshold)

| kind | drafts | with a hint |
|---|---|---|
| duplicate | 73 | 69 (95%) |
| hard_negative | 30 | 4 (13%) |
| novel | 22 | 0 (0%) |
| recurrence | 23 | 20 (87%) |
