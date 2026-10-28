from typing import Any

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import IndirectObject


def has_digital_signatures(reader: PdfReader) -> bool:
    """Detect signed fields or a document certification signature without reading contents."""
    root = reader.trailer.get("/Root")
    permissions = root.get("/Perms") if root else None
    if permissions and permissions.get("/DocMDP") is not None:
        return True
    form = root.get("/AcroForm") if root else None
    fields = form.get("/Fields", []) if form else []
    pending: list[tuple[Any, str | None]] = [(reference, None) for reference in fields]
    visited: set[tuple[int, int] | int] = set()
    while pending and len(visited) < 10_000:
        reference, inherited_type = pending.pop()
        key: tuple[int, int] | int = (
            (reference.idnum, reference.generation)
            if isinstance(reference, IndirectObject)
            else id(reference)
        )
        if key in visited:
            continue
        visited.add(key)
        try:
            field = reference.get_object()
        except (AttributeError, PyPdfError):
            continue
        field_type = str(field.get("/FT", inherited_type or ""))
        if field_type == "/Sig" and field.get("/V") is not None:
            return True
        pending.extend((child, field_type) for child in field.get("/Kids", []))
    return False
