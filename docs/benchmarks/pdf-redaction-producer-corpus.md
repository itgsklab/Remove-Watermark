# PDF Redaction Producer Corpus

Project-authored fixtures exported by real installed applications and checked through the production redaction backend.

- Status: **pass**
- Samples: 3
- Producers: 3
- Passed: 3
- Mismatches: 0

| Producer | Version | Target removed | Unaffected pages preserved | Result |
| --- | --- | --- | --- | --- |
| Google Chrome | 154.0.8037.93 | true | true | pass |
| LibreOfficeDev | 26.8.0.0.alpha0 2c87e51eeaa2b413ff4ae097b2705eea1995d8e5 | true | true | pass |
| Microsoft Word for Mac | 16.110 | true | true | pass |

Each manifest entry pins the exported PDF and source digests, source record, producer version, target region, and manual-review state.
