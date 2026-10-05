import argparse
import hashlib
import json
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from wmrm.adapters.pdf.codecv import CodeCvPdfInspector


def probe_export(
    source_path: Path,
    *,
    sample_id: str,
    template_version: str,
    provenance: str,
) -> dict:
    source_path = source_path.resolve()
    source_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    reader = PdfReader(BytesIO(source_bytes), strict=False)
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    inspection = CodeCvPdfInspector(
        max_pages=1000, max_content_bytes=100_000_000
    ).inspect(source_path, source_sha256)
    candidates = list(inspection.candidates)
    confirmed_count = sum(item.classification == "confirmed" for item in candidates)
    return {
        "id": sample_id,
        "provenance": provenance,
        "template_version": template_version,
        "file": source_path.name,
        "sha256": source_sha256,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "page_count": len(reader.pages),
        "source_record": None,
        "permission_note": "REPLACE: record who created this test export and its permitted use.",
        "review_required": True,
        "expected": {
            "match_status": inspection.match_status,
            "candidate_count": len(candidates),
            "confirmed_count": confirmed_count,
            "candidate_pages": sorted({item.page_number for item in candidates}),
            "clean_match_status": (
                "not_found" if candidates and confirmed_count == len(candidates) else None
            ),
        },
        "observed_resources": sorted(
            {item.resource_name for item in candidates if item.resource_name}
        ),
        "review_note": (
            "These values were observed automatically. Verify the source, permission, candidate "
            "pages and expected cleanup behavior, then set review_required to false."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a review-required manifest entry for a CodeCV export."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--id", required=True)
    parser.add_argument("--template-version", required=True)
    parser.add_argument(
        "--provenance",
        choices=("private_export", "redistributable_export"),
        default="private_export",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = probe_export(
        args.input,
        sample_id=args.id,
        template_version=args.template_version,
        provenance=args.provenance,
    )
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
