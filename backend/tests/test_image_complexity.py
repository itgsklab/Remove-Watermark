from types import SimpleNamespace

from PIL import Image

from wmrm.adapters.images.complexity import ImageComplexityInspector
from wmrm.benchmarks.image_quality import generate_cases


def test_complexity_preflight_matches_synthetic_benchmark(tmp_path) -> None:
    inspector = ImageComplexityInspector()
    risks: dict[str, str] = {}
    for case in generate_cases():
        path = tmp_path / f"{case.case_id}.png"
        Image.fromarray(case.watermarked).save(path)
        region = SimpleNamespace(**case.region)
        risks[case.case_id] = inspector.inspect(path, [region])[0].risk

    assert risks["flat"] == "low"
    assert risks["gradient"] == "low"
    assert risks["stripes"] == "high"
    assert risks["structure"] == "high"
    assert risks["texture"] == "high"


def test_complexity_preflight_reports_explainable_scores(tmp_path) -> None:
    case = next(item for item in generate_cases() if item.case_id == "stripes")
    path = tmp_path / "stripes.png"
    Image.fromarray(case.watermarked).save(path)

    result = ImageComplexityInspector().inspect(
        path, [SimpleNamespace(**case.region)]
    )[0]

    assert result.periodicity_score >= 0.8
    assert result.structure_score >= 0.45
    assert result.context_pixels > 0
    assert any("周期纹理" in reason for reason in result.reasons)
