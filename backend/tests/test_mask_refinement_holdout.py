import json
import subprocess
import sys
from pathlib import Path

from wmrm.benchmarks.mask_refinement import run_mask_refinement_benchmark

FIXTURES = Path(__file__).parent / "fixtures"
HOLDOUT = FIXTURES / "mask_refinement_holdout"
DEVELOPMENT = FIXTURES / "vlm_localization" / "mask-refinement-photo-manifest.json"


def test_holdout_builder_is_reproducible_disjoint_and_audited(tmp_path: Path) -> None:
    subprocess.run([sys.executable, str(HOLDOUT / "build_corpus.py")], check=True)
    holdout = json.loads((HOLDOUT / "manifest.json").read_text())
    development = json.loads(DEVELOPMENT.read_text())

    holdout_sources = {sample["source_group"] for sample in holdout["samples"]}
    development_sources = {sample["source_group"] for sample in development["samples"]}
    holdout_digests = {sample["source_sha256"] for sample in holdout["samples"]}
    development_digests = {sample["source_sha256"] for sample in development["samples"]}
    assert holdout["corpus_role"] == "independent_holdout"
    assert holdout["frozen_before_model_inference"] is True
    assert len(holdout["samples"]) == 16
    assert len(holdout_sources) == 8
    assert len(holdout_digests) == 8
    assert holdout_sources.isdisjoint(development_sources)
    assert holdout_digests.isdisjoint(development_digests)

    report = run_mask_refinement_benchmark(
        HOLDOUT / "manifest.json",
        HOLDOUT / "contract-predictions.json",
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
