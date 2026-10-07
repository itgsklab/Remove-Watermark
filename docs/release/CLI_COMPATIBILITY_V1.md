# CLI compatibility contract v1

This contract defines the automation surface targeted for the first public `0.1.0` release. The
package is on `0.1.0rc1` after passing the Linux, macOS and Windows release-candidate evidence gate.
The machine-readable source of truth is
[`packaging/cli-contract-v1.json`](../../packaging/cli-contract-v1.json).

## Stable surface

- The executable name is `wmrm`.
- The v1 commands are `doctor`, `pdf-deep`, `pdf-redact`, `image-plan`, `image-apply`,
  `docx-plan`, `docx-apply`, `codecv-plan` and `codecv-apply`.
- `--json` writes one success object to standard output or one error object to standard error.
- A success envelope contains exactly `ok`, `command` and `result`.
- An error envelope contains exactly `ok`, `error` and `exit_code`; `error` contains `code` and
  `message`.
- Result objects may gain fields in compatible releases. Fields listed for each command in the
  machine-readable contract will not be removed or change meaning within contract v1.
- Human-readable messages may change and must not be used as automation identifiers. Consumers
  should use error and warning codes.

## Exit codes

| Code | Contract meaning |
|---:|---|
| `0` | Success. |
| `2` | Command syntax or argument parsing failed. |
| `3` | Input, output, saved plan or acknowledgement value is invalid. |
| `4` | A required risk acknowledgement is missing. |
| `5` | Processing or output writing failed. |

## Saved plans

The `image_inpaint`, `docx_object_removal` and `codecv_object_removal` plan kinds use
`schema_version: 1`. Readers must reject unknown schema versions. Plan fields may gain optional
evidence, but removing a field, changing coordinate meaning or changing digest semantics requires a
new schema version.

Plans are review artifacts rather than authorization tokens. Apply commands verify the plan digest,
rescan the source and require current risk acknowledgements. A changed source or candidate location
must produce a new plan.

## Compatibility gate

`python packaging/verify_wheel_install.py` builds an isolated wheel and checks the command list,
success and error envelopes, required result keys, all five exit codes, all three plan schemas and real
execution of every processing command. The release-readiness workflow runs this gate on Linux,
macOS and Windows. Additive result fields remain compatible; any other contract change must update
the contract version and this document.

Passing runs write a JSON evidence report containing the source commit and dirty state, contract and
wheel SHA-256 values, runtime platform, verified commands, exit codes and plan schemas. CI retains
one report for each operating system so a release decision can refer to concrete inputs instead of
the workflow status alone.

After the matrix completes, `python packaging/verify_release_evidence.py` requires exactly one
Linux, macOS and Windows report. Every report must be passing, come from the same expected clean
commit, match the committed v1 contract and development package version, use Python 3.12.10, and
cover the complete command, exit-code and plan-schema surface. The resulting aggregate JSON pins
the SHA-256 of each platform report and is the machine-readable prerequisite for preparing a release
candidate.

`python packaging/prepare_release_candidate.py` revalidates that aggregate against the three raw
reports and the current clean Git commit before producing a version-change plan. Applying the plan
updates every Python, npm and desktop version source and regenerates release metadata transactionally;
it does not commit, tag or publish. See [release-candidate preparation](RELEASE_CANDIDATE.md).
