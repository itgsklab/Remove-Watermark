# CodeCV export corpus audit

Status: **generated_only** · Samples: 3 · Real exports: 0 · Cleanup: 2/2 · Mismatches: 0

`generated_only` means the audit harness is working, but no real CodeCV export has been supplied. It must not be treated as template compatibility evidence.

| Sample | Provenance | Template | Pages | Source | Candidates | Cleanup | Mismatches |
|---|---|---|---:|---|---:|---|---:|
| generated-basic-v1 | repository_generated | synthetic-basic-v1 | 1 | matched | 1 | pass | 0 |
| generated-gs-evenodd-v2 | repository_generated | synthetic-gs-fstar-v2 | 2 | matched | 2 | pass | 0 |
| generated-negative-v1 | repository_generated | synthetic-negative-v1 | 2 | not_found | 0 | n/a | 0 |

## Sample details

### generated-basic-v1

- File: `generated-basic-v1.pdf` (`8e5db68c5b96a8d8cf703945d8262b9463f8dd16953823dab0b338378b1479ba`)
- Text SHA-256: `548698286702b9d0e4d480b326b78862850ee53210fa1fb392ebfb3429a831d7`
- Candidate pages: `[1]`
- Pattern resources: `['/Watermark1']`
- Cleanup removed: `1`
- Mismatches: none

### generated-gs-evenodd-v2

- File: `generated-gs-evenodd-v2.pdf` (`95bb72db82f003c423471bb0e7f9f8744c42720e7c3c301d1170340febd7db37`)
- Text SHA-256: `1a1737f206fc4bcd92aba1bf89dfbb815d3c9a837f56cc3745155aef90f5315b`
- Candidate pages: `[1, 2]`
- Pattern resources: `['/TileP7']`
- Cleanup removed: `2`
- Mismatches: none

### generated-negative-v1

- File: `generated-negative-v1.pdf` (`713839632e0716c0f3e0e2d239f3f9f8b08664fbd681581be74afe7312deff58`)
- Text SHA-256: `1a1737f206fc4bcd92aba1bf89dfbb815d3c9a837f56cc3745155aef90f5315b`
- Candidate pages: `[]`
- Pattern resources: `[]`
- Cleanup removed: `0`
- Mismatches: none
