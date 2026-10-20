import json
import subprocess
import sys
from pathlib import Path

from wmrm.benchmarks.mask_refinement import run_mask_refinement_benchmark

FIXTURES = Path(__file__).parent / "fixtures"
CONFIRMATION = FIXTURES / "mask_refinement_confirmation"
DEVELOPMENT = FIXTURES / "vlm_localization" / "mask-refinement-photo-manifest.json"
FIRST_HOLDOUT = FIXTURES / "mask_refinement_holdout" / "manifest.json"


def test_confirmation_builder_is_reproducible_disjoint_and_audited(tmp_path: Path) -> None:
    subprocess.run([sys.executable, str(CONFIRMATION / "build_corpus.py")], check=True)
    confirmation = json.loads((CONFIRMATION / "manifest.json").read_text())
    development = json.loads(DEVELOPMENT.read_text())
    first_holdout = json.loads(FIRST_HOLDOUT.read_text())

    prior_samples = development["samples"] + first_holdout["samples"]
    prior_sources = {sample["source_group"] for sample in prior_samples}
    prior_digests = {sample["source_sha256"] for sample in prior_samples}
    confirmation_sources = {sample["source_group"] for sample in confirmation["samples"]}
    confirmation_digests = {sample["source_sha256"] for sample in confirmation["samples"]}

    assert confirmation["corpus_role"] == "independent_confirmation"
    assert confirmation["frozen_before_model_inference"] is True
    assert len(confirmation["samples"]) == 16
    assert len(confirmation_sources) == 8
    assert len(confirmation_digests) == 8
    assert confirmation_sources.isdisjoint(prior_sources)
    assert confirmation_digests.isdisjoint(prior_digests)

    report = run_mask_refinement_benchmark(
        CONFIRMATION / "manifest.json",
        CONFIRMATION / "contract-predictions.json",
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
        min_sample_count=16,
        min_negative_count=8,
        min_category_count=4,
    )
    assert report["corpus"] == {
        "kind": "provenance_photo_pairs",
        "provenance_gate": "pass",
        "pair_count": 8,
        "source_count": 8,
        "contains_user_data": False,
    }
    assert report["summary"]["evidence_gate"] == "pass"
