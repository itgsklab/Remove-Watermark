# Stable release gate for v0.1.0

`v0.1.0` remains pending after the immutable `v0.1.0rc1` and `v0.1.0rc2` Web prereleases. A stable
tag must not be created only because CI is green. The release maintainer must supply a reviewable
feedback record and pass the machine-readable gate.

The committed policy in `packaging/stable-release-policy.json` pins both RC source commits and every
published release-asset SHA-256 digest. It also preserves these contracts:

- Vue Web UI plus Python/FastAPI local service; no native applications;
- Linux, macOS and Windows package/CLI evidence;
- VLM disabled by default, no automatic model download and mandatory manual review;
- no model weights or private planning/status files in release assets;
- clean installation, browser acceptance for `/` and `/settings`, and a privacy scan;
- at least one real feedback source and no unresolved reproducible critical or high issue.

Validate the committed policy without claiming that stable is ready:

```bash
make stable-release-policy-check
```

Copy `packaging/stable-feedback.example.json` into the ignored `work/` directory and replace every
placeholder with actual review evidence. A source can be a GitHub issue, a documented maintainer
acceptance run or another traceable test report. Do not put user files, personal information, local
paths, tokens or private sample contents in the record.

```bash
cp packaging/stable-feedback.example.json work/stable-feedback.json
python packaging/verify_stable_release.py \
  --feedback work/stable-feedback.json \
  --require-ready \
  --output-json work/stable-readiness.json
```

The command fails when feedback is absent, approval is missing, required runtime checks did not pass,
the VLM opt-in contract changed, or a reproducible critical/high issue remains open or deferred. A
passing result authorizes preparation and verification of a stable-version commit; it does not create
a commit, tag, GitHub Release or PyPI upload.
