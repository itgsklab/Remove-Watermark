# VLM photo-scene gate benchmark

Gate classification: Precision **1.000** · Recall **1.000** · Specificity **1.000**
Pair stability: **21/21** · Independent photo sources: **16/10** · Source evidence gate: **pass**
Eligible photo localization: Precision **0.750** · Recall **0.947** · F1 **0.837**

| Sample | Expected | Eligible | Entropy | Colors | Luma SD | Flat | Orientation H | Routes | Correct |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| real-horizon-corner | photo | yes | 5.5563 | 212 | 74.5819 | 0.5329 | 3.7159 | color-diversity, continuous-tone | yes |
| real-horizon-translucent | photo | yes | 5.5659 | 213 | 74.5023 | 0.5260 | 3.7576 | color-diversity, continuous-tone | yes |
| real-night-multiline | photo | yes | 6.4993 | 471 | 56.8243 | 0.2956 | 4.1455 | color-diversity, continuous-tone, distributed-detail | yes |
| clean-horizon-negative | photo | yes | 5.1557 | 190 | 67.3696 | 0.5466 | 3.6999 | color-diversity, continuous-tone | yes |
| clean-night-negative | photo | yes | 5.6467 | 400 | 44.8110 | 0.4503 | 4.1261 | color-diversity, continuous-tone, distributed-detail | yes |
| clean-project-ui-negative | other | no | 2.7627 | 76 | 33.1175 | 0.8213 | 3.5805 | — | yes |
| paired-photo-horizon-negative | photo | yes | 5.6377 | 201 | 70.7650 | 0.5034 | 3.6772 | color-diversity, continuous-tone | yes |
| paired-photo-horizon-positive | photo | yes | 5.6974 | 212 | 70.4402 | 0.5075 | 3.6650 | color-diversity, continuous-tone | yes |
| paired-photo-night-negative | photo | yes | 5.8105 | 385 | 47.5592 | 0.4229 | 4.1277 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-photo-night-positive | photo | yes | 5.8327 | 389 | 47.7595 | 0.4172 | 4.1302 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-pia24642-negative | photo | yes | 6.4548 | 93 | 27.4791 | 0.2032 | 3.8808 | continuous-tone | yes |
| paired-pia24642-positive | photo | yes | 6.5462 | 128 | 31.2644 | 0.2057 | 3.8758 | color-diversity, continuous-tone | yes |
| paired-as11-40-5878-negative | photo | yes | 7.1603 | 16 | 43.5610 | 0.0272 | 4.1537 | continuous-tone, distributed-detail | yes |
| paired-as11-40-5878-positive | photo | yes | 7.1624 | 27 | 43.5898 | 0.0270 | 4.1531 | continuous-tone, distributed-detail | yes |
| paired-iss042e097549-negative | photo | yes | 6.7489 | 197 | 86.4510 | 0.4333 | 2.7482 | color-diversity, continuous-tone | yes |
| paired-iss042e097549-positive | photo | yes | 6.7876 | 205 | 84.8332 | 0.4352 | 2.7005 | color-diversity, continuous-tone | yes |
| paired-pia11141-negative | photo | yes | 3.5689 | 113 | 63.5991 | 0.6790 | 3.6139 | continuous-tone | yes |
| paired-pia11141-positive | photo | yes | 3.6777 | 113 | 63.5349 | 0.6610 | 3.6917 | continuous-tone | yes |
| paired-pia00254-negative | photo | yes | 6.3973 | 115 | 64.7068 | 0.2514 | 4.0761 | continuous-tone, distributed-detail | yes |
| paired-pia00254-positive | photo | yes | 6.4266 | 143 | 64.0040 | 0.2558 | 4.0756 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-pia20284-negative | photo | yes | 7.6705 | 228 | 57.7837 | 0.2134 | 3.9955 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-pia20284-positive | photo | yes | 7.6715 | 228 | 57.7948 | 0.1998 | 4.0051 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-pia17792-negative | photo | yes | 3.5691 | 317 | 34.3808 | 0.8387 | 4.0954 | distributed-detail | yes |
| paired-pia17792-positive | photo | yes | 3.6489 | 317 | 34.2569 | 0.8345 | 4.0853 | distributed-detail | yes |
| paired-pia11727-negative | photo | yes | 7.2844 | 764 | 40.1424 | 0.0836 | 4.1356 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-pia11727-positive | photo | yes | 7.2890 | 790 | 40.2279 | 0.0829 | 4.1362 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-commons-38778875-negative | photo | yes | 7.3288 | 304 | 55.4634 | 0.1816 | 4.0889 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-commons-38778875-positive | photo | yes | 7.3724 | 304 | 56.3270 | 0.1850 | 4.0846 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-commons-59873545-negative | photo | yes | 6.8841 | 332 | 38.4976 | 0.0285 | 4.0761 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-commons-59873545-positive | photo | yes | 6.8941 | 339 | 38.6231 | 0.0284 | 4.0789 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-commons-14666867-negative | photo | yes | 7.5311 | 218 | 65.3344 | 0.0959 | 4.0711 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-commons-14666867-positive | photo | yes | 7.5632 | 218 | 66.5716 | 0.0985 | 4.0645 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-commons-74184357-negative | photo | yes | 7.1939 | 16 | 37.2844 | 0.0209 | 4.0965 | continuous-tone, distributed-detail | yes |
| paired-commons-74184357-positive | photo | yes | 7.1973 | 27 | 37.3708 | 0.0207 | 4.0971 | continuous-tone, distributed-detail | yes |
| paired-commons-144326190-negative | photo | yes | 7.4376 | 109 | 47.0140 | 0.0270 | 4.0723 | continuous-tone, distributed-detail | yes |
| paired-commons-144326190-positive | photo | yes | 7.4970 | 111 | 48.1323 | 0.0310 | 4.0760 | continuous-tone, distributed-detail | yes |
| paired-commons-201054816-negative | photo | yes | 7.1001 | 390 | 52.4772 | 0.3212 | 3.9483 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-commons-201054816-positive | photo | yes | 7.1051 | 390 | 52.6227 | 0.3099 | 3.9508 | color-diversity, continuous-tone, distributed-detail | yes |
| paired-dashboard-negative | other | no | 2.4758 | 49 | 83.7334 | 0.8196 | 3.4508 | — | yes |
| paired-dashboard-positive | other | no | 2.6214 | 49 | 83.6212 | 0.8006 | 3.6240 | — | yes |
| paired-document-negative | other | no | 2.0304 | 41 | 20.4161 | 0.8000 | 3.0704 | — | yes |
| paired-document-positive | other | no | 2.1524 | 77 | 20.9189 | 0.7851 | 3.2466 | — | yes |
| paired-code-editor-negative | other | no | 2.0104 | 25 | 13.1854 | 0.8871 | 3.5889 | — | yes |
| paired-code-editor-positive | other | no | 2.2010 | 54 | 16.7146 | 0.8712 | 3.5777 | — | yes |
| paired-poster-negative | other | no | 1.1677 | 62 | 39.7253 | 0.8154 | 3.4138 | — | yes |
| paired-poster-positive | other | no | 1.2309 | 73 | 39.8111 | 0.8059 | 3.4675 | — | yes |
| paired-mobile-feed-negative | other | no | 3.1065 | 66 | 26.8274 | 0.8234 | 3.4708 | — | yes |
| paired-mobile-feed-positive | other | no | 3.1909 | 66 | 27.3333 | 0.8127 | 3.5262 | — | yes |

The gate is release-ready only when source evidence, classification, pair stability, and eligible-photo localization requirements all pass.
