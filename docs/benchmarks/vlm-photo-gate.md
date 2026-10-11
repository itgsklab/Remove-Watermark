# VLM photo-scene gate benchmark

Gate classification: Precision **1.000** · Recall **0.680** · Specificity **1.000**
Pair stability: **13/15** · Independent photo sources: **10/10** · Source evidence gate: **pass**
Eligible photo localization: Precision **0.909** · Recall **0.769** · F1 **0.833**

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
| paired-pia24642-negative | photo | no | 6.4548 | 93 | no |
| paired-pia24642-positive | photo | yes | 6.5462 | 128 | yes |
| paired-as11-40-5878-negative | photo | no | 7.1603 | 16 | no |
| paired-as11-40-5878-positive | photo | no | 7.1624 | 27 | no |
| paired-iss042e097549-negative | photo | yes | 6.7489 | 197 | yes |
| paired-iss042e097549-positive | photo | yes | 6.7876 | 205 | yes |
| paired-pia11141-negative | photo | no | 3.5689 | 113 | no |
| paired-pia11141-positive | photo | no | 3.6777 | 113 | no |
| paired-pia00254-negative | photo | no | 6.3973 | 115 | no |
| paired-pia00254-positive | photo | yes | 6.4266 | 143 | yes |
| paired-pia20284-negative | photo | yes | 7.6705 | 228 | yes |
| paired-pia20284-positive | photo | yes | 7.6715 | 228 | yes |
| paired-pia17792-negative | photo | no | 3.5691 | 317 | no |
| paired-pia17792-positive | photo | no | 3.6489 | 317 | no |
| paired-pia11727-negative | photo | yes | 7.2844 | 764 | yes |
| paired-pia11727-positive | photo | yes | 7.2890 | 790 | yes |
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

The gate is release-ready only when source evidence, classification, pair stability, and eligible-photo localization requirements all pass.
