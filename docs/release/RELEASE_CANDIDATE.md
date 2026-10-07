# Release-candidate preparation

The first release candidate may be prepared only from a clean checkout of the exact commit that
passed the Linux, macOS and Windows release-readiness matrix. Download the aggregate summary and
all three platform reports from that workflow run into an ignored `work/` directory.

Validate the evidence and write a reviewable change plan without modifying the repository:

```bash
python packaging/prepare_release_candidate.py \
  --summary work/release-evidence/release-readiness-summary.json \
  --evidence work/release-evidence/platforms \
  --rc-number 1 \
  --plan-json work/release-evidence/rc1-plan.json
```

The command rejects a dirty checkout, a summary for another commit, missing or duplicate platform
reports, changed evidence digests, and reports that no longer match the committed CLI contract. The
plan identifies the source commit, input evidence digests, old and new Python/npm versions, and every
version source that would change.

After reviewing the plan, repeat the command with `--apply`. This changes the Python version to
`0.1.0rc1`, the npm version to `0.1.0-rc.1`, updates all backend, frontend and desktop version
sources, and regenerates the dependency inventory and SPDX SBOM. Writes are rolled back if metadata
generation or its freshness check fails.

```bash
python packaging/prepare_release_candidate.py \
  --summary work/release-evidence/release-readiness-summary.json \
  --evidence work/release-evidence/platforms \
  --rc-number 1 \
  --plan-json work/release-evidence/rc1-applied.json \
  --apply
```

The tool does not commit, tag, upload or publish anything. The resulting changes must pass the full
release-readiness matrix again as the release-candidate commit before any package publication.
