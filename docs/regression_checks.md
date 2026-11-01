# Release comparison checks

Versions used (30+ reviews each): 18.18.1 (53), 18.19.2 (77), 18.20.2 (81), 18.21.1 (143)
Rules under test: both versions need 30+ reviews, adjusted p < 0.01, and a rise of at least 1.5x.

## 1. No-change test (1 to 2 star share)
2000 shuffles of real reviews across 4 versions, flags raised: **18 (0.9%)**. Any flag here is a false alarm.

## 1b. No-change test including all 95 themes
150 shuffles, any flag (score or any theme): **0 (0.0%)**.

## 2. Injected spike (1 to 2 star share)
Previous version has 25% of reviews at 1 to 2 stars. The new version has the share below. 1000 simulations each.

| New share | Rise | Reviews per version | Flagged |
|---|---|---|---|
| 25% | none | 80 | 0% |
| 30% | 1.2x | 80 | 1% |
| 35% | 1.4x | 80 | 9% |
| 40% | 1.6x | 80 | 23% |
| 50% | 2.0x | 80 | 74% |
| 60% | 2.4x | 80 | 97% |
| 25% | none | 150 | 0% |
| 30% | 1.2x | 150 | 5% |
| 35% | 1.4x | 150 | 22% |
| 40% | 1.6x | 150 | 57% |
| 50% | 2.0x | 150 | 96% |
| 60% | 2.4x | 150 | 100% |

The 1.5x rule applies to the shares actually observed in each sample, so a small real rise is flagged only when chance also pushes the observed difference up. That is why 1.2x to 1.4x rows flag rarely, not never.

## 3. One theme spikes among 95 others
95 themes stay at 5% of reviews in both versions. One theme goes from 5% to the share below. 80 reviews per version, 500 simulations each.

| Theme share in new version | Flagged |
|---|---|
| 5% | 0% |
| 15% | 2% |
| 20% | 11% |
| 30% | 62% |
| 40% | 96% |

Note: the 5% row is the no-change case for this theme.
