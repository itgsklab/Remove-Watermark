import json
import shutil
import subprocess
import sys
from pathlib import Path

from wmrm.benchmarks.mask_refinement import run_mask_refinement_benchmark

FIXTURES = Path(__file__).parent / "fixtures"
HOLDOUT = FIXTURES / "mask_refinement_holdout"
DEVELOPMENT = FIXTURES / "vlm_localization" / "mask-refinement-photo-manifest.json"


def test_holdout_builder_is_reproducible_disjoint_and_audited(tmp_path: Path) -> None:
    generated_root = tmp_path / "fixtures"
    generated = generated_root / HOLDOUT.name
    shutil.copytree(HOLDOUT, generated)
    source = FIXTURES / f"{HOLDOUT.name}_sources"
    shutil.copytree(source, generated_root / source.name)
    development_copy = generated_root / DEVELOPMENT.relative_to(FIXTURES)
    development_copy.parent.mkdir(parents=True)
    shutil.copy2(DEVELOPMENT, development_copy)
    subprocess.run([sys.executable, str(generated / "build_corpus.py")], check=True)
    holdout = json.loads((generated / "manifest.json").read_text())
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
        generated / "manifest.json",
        generated / "contract-predictions.json",
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
