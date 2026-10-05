from dataclasses import dataclass
from pathlib import Path

from wmrm.domain.enums import AssetKind


@dataclass(frozen=True, slots=True)
class InspectedFile:
    kind: AssetKind
    media_type: str
    size_bytes: int
    sha256: str
    stored_path: Path

