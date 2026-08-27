"""Canonical in-memory model for a CSR register block."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Literal


AccessType = Literal["RW", "RO", "W1C"]


@dataclass(frozen=True)
class Field:
    """One named bit field within a 32-bit register."""

    name: str
    msb: int
    lsb: int
    access: AccessType
    reset: int

    @property
    def width(self) -> int:
        return self.msb - self.lsb + 1


@dataclass(frozen=True)
class Register:
    """One register at a local byte offset."""

    name: str
    offset: int
    fields: tuple[Field, ...]


@dataclass(frozen=True)
class RegisterBlock:
    """Canonical IR root for one fixed-width CSR block."""

    name: str
    data_width: int
    address_width: int
    registers: tuple[Register, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation of this IR."""

        return asdict(self)

    def to_json(self) -> str:
        """Serialize deterministically for review and generated-file diffs."""

        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"

