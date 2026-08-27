"""Strict CSV parser for CSRForge v0.1."""

from __future__ import annotations

from collections import OrderedDict
import csv
from pathlib import Path
from typing import cast

from .model import AccessType, Field, Register, RegisterBlock


REQUIRED_COLUMNS = ("Register", "Offset", "Field", "Bits", "Access", "Reset")


class ParseError(ValueError):
    """Raised when CSV text cannot be converted into typed IR values."""


def _parse_integer(text: str, *, row_number: int, column: str) -> int:
    """Parse decimal or prefixed binary/octal/hexadecimal integer text."""

    token = text.strip().replace("_", "")
    lowered = token.lower()
    base = 0 if lowered.startswith(("0x", "+0x", "-0x", "0b", "+0b", "-0b", "0o", "+0o", "-0o")) else 10

    try:
        return int(token, base)
    except ValueError as exc:
        raise ParseError(
            f"Row {row_number}: invalid {column} integer {text!r}."
        ) from exc


def _parse_bits(text: str, *, row_number: int) -> tuple[int, int]:
    """Parse a bit position or msb:lsb range without applying range rules."""

    token = text.strip()
    parts = token.split(":")

    if len(parts) == 1:
        bit = _parse_integer(parts[0], row_number=row_number, column="Bits")
        return bit, bit

    if len(parts) == 2 and all(part.strip() for part in parts):
        msb = _parse_integer(parts[0], row_number=row_number, column="Bits MSB")
        lsb = _parse_integer(parts[1], row_number=row_number, column="Bits LSB")
        return msb, lsb

    raise ParseError(f"Row {row_number}: invalid Bits syntax {text!r}.")


class CsvParser:
    """Parse strict v0.1 CSV rows into the canonical dataclass model."""

    def __init__(self, path: str | Path, *, block_name: str = "csr_regs"):
        self.path = Path(path)
        self.block_name = block_name

    def parse(self) -> RegisterBlock:
        grouped: OrderedDict[tuple[str, int], list[Field]] = OrderedDict()

        try:
            csv_file = self.path.open("r", encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise ParseError(f"Cannot open CSV file {self.path}: {exc}") from exc

        with csv_file:
            reader = csv.DictReader(csv_file)
            actual_columns = tuple(reader.fieldnames or ())
            if actual_columns != REQUIRED_COLUMNS:
                raise ParseError(
                    "CSV header must be exactly "
                    f"{','.join(REQUIRED_COLUMNS)}; got "
                    f"{','.join(actual_columns) or '<empty>'}."
                )

            parsed_rows = 0
            for row_number, row in enumerate(reader, start=2):
                values = {name: (row.get(name) or "").strip() for name in REQUIRED_COLUMNS}

                if not any(values.values()):
                    continue

                missing = [name for name, value in values.items() if not value]
                if missing:
                    raise ParseError(
                        f"Row {row_number}: missing required cell(s): {', '.join(missing)}."
                    )

                offset = _parse_integer(
                    values["Offset"], row_number=row_number, column="Offset"
                )
                msb, lsb = _parse_bits(values["Bits"], row_number=row_number)
                reset = _parse_integer(
                    values["Reset"], row_number=row_number, column="Reset"
                )

                # Access validity is a semantic rule checked in the next slice.
                access = cast(AccessType, values["Access"].upper())
                field = Field(
                    name=values["Field"],
                    msb=msb,
                    lsb=lsb,
                    access=access,
                    reset=reset,
                )
                grouped.setdefault(
                    (values["Register"], offset), []
                ).append(field)
                parsed_rows += 1

        if parsed_rows == 0:
            raise ParseError("CSV contains no register field rows.")

        registers = tuple(
            Register(name=name, offset=offset, fields=tuple(fields))
            for (name, offset), fields in grouped.items()
        )
        return RegisterBlock(
            name=self.block_name,
            data_width=32,
            address_width=32,
            registers=registers,
        )

