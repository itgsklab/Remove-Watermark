# VLM photo-scene gate benchmark

Gate classification: Precision **1.000** · Recall **1.000** · Specificity **1.000**
Pair stability: **7/7** · Independent photo sources: **2/10** · Source evidence gate: **fail**
Eligible photo localization: Precision **1.000** · Recall **1.000** · F1 **1.000**

| Sample | Expected | Eligible | Entropy | Colors | Correct |
|---|---:|---:|---:|---:|---:|
| real-horizon-corner | photo | yes | 5.5563 | 212 | yes |
| real-horizon-translucent | photo | yes | 5.5659 | 213 | yes |
| real-night-multiline | photo | yes | 6.4993 | 471 | yes |
| clean-horizon-negative | photo | yes | 5.1557 | 190 | yes |
| clean-night-negative | photo | yes | 5.6467 | 400 | yes |
| clean-project-ui-negative | other | no | 2.7627 | 76 | yes |
| paired-photo-horizon-negative | photo | yes | 5.6377 | 201 | yes |
| paired-photo-horizon-positive | photo | yes | 5.6974 | 212 | yes |
| paired-photo-night-negative | photo | yes | 5.8105 | 385 | yes |
| paired-photo-night-positive | photo | yes | 5.8327 | 389 | yes |
| paired-dashboard-negative | other | no | 2.4758 | 49 | yes |
| paired-dashboard-positive | other | no | 2.6214 | 49 | yes |
| paired-document-negative | other | no | 2.0304 | 41 | yes |
| paired-document-positive | other | no | 2.1524 | 77 | yes |
| paired-code-editor-negative | other | no | 2.0104 | 25 | yes |
| paired-code-editor-positive | other | no | 2.2010 | 54 | yes |
| paired-poster-negative | other | no | 1.1677 | 62 | yes |
| paired-poster-positive | other | no | 1.2309 | 73 | yes |
| paired-mobile-feed-negative | other | no | 3.1065 | 66 | yes |
| paired-mobile-feed-positive | other | no | 3.1909 | 66 | yes |

The gate is not release-ready until independent photo-source evidence passes.
