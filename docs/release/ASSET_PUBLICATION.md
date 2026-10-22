# Release asset publication and recovery

Every Web release has exactly five public assets: `SHA256SUMS`, `release-manifest.json`, the Web
bundle, the Python wheel and the Python source distribution. Build and review them in a Git-ignored
`work/` directory. Do not upload workflow logs, local reports, model files, user samples, status or
planning documents.

## Pre-publication gate

Run the complete asset audit before creating a GitHub Release. Replace the version and source commit
with the reviewed candidate values:

```bash
python packaging/audit_release_assets.py \
  --assets-dir work/releases/0.2.0rc1/public \
  --version 0.2.0rc1 \
  --expected-commit FULL_40_CHARACTER_COMMIT \
  --report-json work/releases/0.2.0rc1/asset-audit.json
```

The audit requires the exact five-file set and cross-checks the manifest, `SHA256SUMS`, sizes,
digests and source commit. It recursively inspects the wheel, source distribution, Web bundle and
nested package archives. It rejects unsafe or duplicate paths, links and special files, private
planning/build paths, environment files, local home paths, high-confidence credential formats,
model-weight formats, excessive nesting and oversized expansion. The JSON report contains only
public names, hashes, counts and the public source commit; keep the report under ignored `work/`
until its contents are reviewed.

Create and push the reviewed tag separately. Create the release as a draft with `--verify-tag`,
upload only the five audited files, inspect the draft in GitHub, and publish it only after the names,
target commit and prerelease status match the plan. Do not rely on automatic tag creation. If GitHub
immutable releases are enabled, publication permanently locks the tag and assets, which makes the
draft review the final correction point.

## Post-publication download verification

Download every asset into a new empty ignored directory. Never verify the original upload directory
as proof of the public download:

```bash
download_dir="$(mktemp -d work/release-download.XXXXXX)"
gh release download v0.2.0rc1 --dir "$download_dir"
python packaging/audit_release_assets.py \
  --assets-dir "$download_dir" \
  --version 0.2.0rc1 \
  --expected-commit FULL_40_CHARACTER_COMMIT \
  --report-json work/releases/0.2.0rc1/download-audit.json
```

After the release and all five asset digests are pinned in the stable release policy, bind the
download to that committed record as well:

```bash
python packaging/audit_release_assets.py \
  --assets-dir "$download_dir" \
  --version 0.2.0rc1 \
  --expected-commit FULL_40_CHARACTER_COMMIT \
  --policy packaging/stable-release-policy.json \
  --tag v0.2.0rc1
```

A failed or interrupted download fails digest validation. Delete that temporary directory and
download the complete five-file set again; do not copy missing files from the original build.
The manually dispatched `Release asset audit` GitHub Actions workflow performs the same fresh
download with read-only repository permission, verifies the release tag targets the expected full
commit, and retains only the privacy-safe JSON audit report.

## Recovery and rollback

Published assets are immutable evidence. Do not replace an asset under the same name, move a tag to
a different commit or silently edit a manifest after publication.

For a functional defect without sensitive-data exposure:

1. Keep the affected release and hashes available as evidence, mark it as a prerelease when the
   repository permits that edit, and add a clear known-issue notice.
2. Open a blocking issue that names the affected tag and public asset hashes without including user
   data or local paths.
3. Fix the defect on a new commit, repeat every release gate and publish a higher RC number. The new
   release receives new files, hashes and a new immutable tag.
4. Download and audit the replacement release before directing users to it.

For a confirmed secret, personal-data or private-file exposure:

1. Revoke or rotate the exposed credential first. Preserve only non-sensitive incident metadata,
   asset names and hashes.
2. Remove the affected asset with `gh release delete-asset TAG ASSET --yes`, or remove the release
   through the GitHub incident process when every asset is affected. Immutable-release settings may
   require repository administration or GitHub support.
3. Inspect the tagged Git tree and commit history separately. Removing a release asset does not
   remove content committed to Git.
4. Verify that unauthenticated asset download no longer succeeds, record the result privately, and
   publish a new incremented RC only after the source of the leak is removed and this audit passes.

Rollback never authorizes restoring an older vulnerable asset or bypassing the API, error-code,
platform, human-timing, model-supply-chain or manual-review gates.
