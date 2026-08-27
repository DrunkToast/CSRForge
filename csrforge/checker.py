"""Deterministic semantic validation for CSRForge canonical IR."""

from __future__ import annotations

import re

from .model import Field, RegisterBlock


SUPPORTED_ACCESS_TYPES = frozenset({"RW", "RO", "W1C"})
PORTABLE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ValidationError(ValueError):
    """Raised with every semantic issue found in one validation pass."""

    def __init__(self, issues: list[str]):
        self.issues = tuple(issues)
        detail = "\n".join(f"- {issue}" for issue in self.issues)
        super().__init__(f"CSR specification has {len(self.issues)} error(s):\n{detail}")


class SemanticChecker:
    """Validate a parsed register block without mutating or repairing it."""

    def validate(self, block: RegisterBlock) -> RegisterBlock:
        issues: list[str] = []

        if block.data_width != 32:
            issues.append(
                f"Block data width must be 32, got {block.data_width}."
            )
        if block.address_width != 32:
            issues.append(
                f"Block address width must be 32, got {block.address_width}."
            )
        if not PORTABLE_IDENTIFIER.fullmatch(block.name):
            issues.append(
                f"Block name {block.name!r} is not a portable identifier."
            )

        register_names: dict[str, int] = {}
        register_offsets: dict[int, str] = {}

        for register in block.registers:
            location = f"Register {register.name!r}"

            if not PORTABLE_IDENTIFIER.fullmatch(register.name):
                issues.append(
                    f"{location} is not a portable identifier."
                )

            previous_offset = register_names.get(register.name)
            if previous_offset is not None and previous_offset != register.offset:
                issues.append(
                    f"{location} uses inconsistent offsets "
                    f"0x{previous_offset:08X} and 0x{register.offset:08X}."
                )
            else:
                register_names[register.name] = register.offset

            previous_name = register_offsets.get(register.offset)
            if previous_name is not None and previous_name != register.name:
                issues.append(
                    f"Registers {previous_name!r} and {register.name!r} both use "
                    f"offset 0x{register.offset:08X}."
                )
            else:
                register_offsets[register.offset] = register.name

            if register.offset < 0 or register.offset > 0xFFFF_FFFF:
                issues.append(
                    f"{location} offset {register.offset} is outside the 32-bit "
                    "unsigned address range."
                )
            elif register.offset % 4 != 0:
                issues.append(
                    f"{location} offset 0x{register.offset:08X} is not 4-byte aligned."
                )

            if not register.fields:
                issues.append(f"{location} contains no fields.")
                continue

            field_names: set[str] = set()
            occupied_bits: dict[int, str] = {}

            for field in register.fields:
                self._validate_field(
                    register.name,
                    field,
                    field_names,
                    occupied_bits,
                    issues,
                    block.data_width,
                )

        if issues:
            raise ValidationError(issues)
        return block

    @staticmethod
    def _validate_field(
        register_name: str,
        field: Field,
        field_names: set[str],
        occupied_bits: dict[int, str],
        issues: list[str],
        data_width: int,
    ) -> None:
        location = f"Field {register_name}.{field.name}"

        if not PORTABLE_IDENTIFIER.fullmatch(field.name):
            issues.append(f"{location} is not a portable identifier.")

        if field.name in field_names:
            issues.append(
                f"Register {register_name!r} contains duplicate field name "
                f"{field.name!r}."
            )
        else:
            field_names.add(field.name)

        range_valid = 0 <= field.lsb <= field.msb < data_width
        if not range_valid:
            issues.append(
                f"{location} has invalid bit range {field.msb}:{field.lsb}; "
                f"expected 0 <= lsb <= msb <= {data_width - 1}."
            )
        else:
            overlapping = sorted(
                bit for bit in range(field.lsb, field.msb + 1)
                if bit in occupied_bits
            )
            if overlapping:
                owners = sorted({occupied_bits[bit] for bit in overlapping})
                issues.append(
                    f"{location} overlaps field(s) {', '.join(owners)} at bit(s) "
                    f"{overlapping}."
                )
            else:
                for bit in range(field.lsb, field.msb + 1):
                    occupied_bits[bit] = field.name

        if field.access not in SUPPORTED_ACCESS_TYPES:
            issues.append(
                f"{location} has unsupported access {field.access!r}; "
                "expected RW, RO, or W1C."
            )

        if range_valid:
            maximum_reset = (1 << field.width) - 1
            if field.reset < 0 or field.reset > maximum_reset:
                issues.append(
                    f"{location} reset {field.reset} does not fit its "
                    f"{field.width}-bit width (allowed 0..{maximum_reset})."
                )

