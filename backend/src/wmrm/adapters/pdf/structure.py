from collections.abc import Callable
from typing import Any

STRUCTURE_PROBES: dict[str, Callable[[Any], int]] = {
    "searchable_words": lambda page: len(page.get_text("words")),
    "links": lambda page: len(page.get_links()),
    "form_fields": lambda page: len(list(page.widgets() or [])),
    "annotations": lambda page: len(list(page.annots() or [])),
    "vector_graphics": lambda page: len(page.get_drawings()),
}


def inspect_pdf_page_structure(page: Any) -> dict[str, int | None]:
    """Return privacy-safe per-page structure counts.

    A failed probe is reported as ``None`` instead of failing an otherwise valid processing task.
    Counts are evidence about retained structure, not object-identity or byte-equality claims.
    """
    result: dict[str, int | None] = {}
    for name, probe in STRUCTURE_PROBES.items():
        try:
            result[name] = max(0, int(probe(page)))
        except (RuntimeError, TypeError, ValueError):
            result[name] = None
    return result


def compare_pdf_page_structure(
    source: dict[str, int | None], output: dict[str, int | None]
) -> dict[str, dict[str, int | str | None]]:
    return {
        name: {
            "source_count": source.get(name),
            "output_count": output.get(name),
            "status": _comparison_status(source.get(name), output.get(name)),
        }
        for name in STRUCTURE_PROBES
    }


def _comparison_status(source: int | None, output: int | None) -> str:
    if source is None or output is None:
        return "unavailable"
    if source == 0 and output == 0:
        return "absent"
    if source == output:
        return "count_unchanged"
    if source > 0 and output == 0:
        return "removed"
    if output < source:
        return "count_reduced"
    if source == 0:
        return "created"
    return "count_increased"
