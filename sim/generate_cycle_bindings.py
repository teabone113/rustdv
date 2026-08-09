#!/usr/bin/env python3
"""Generate matching Rust ABI types and direct Verilator C++ port bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TYPE_INFO = {
    "u8": ("u8", "std::uint8_t", 1, 1),
    "u16": ("u16", "std::uint16_t", 2, 2),
    "u32": ("u32", "std::uint32_t", 4, 4),
    "u64": ("u64", "std::uint64_t", 8, 8),
}
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def canonical_hash(document: dict[str, object]) -> int:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "little")


def validate(document: dict[str, object]) -> None:
    if document.get("schema") != "rustdv.cycle-schema/v1":
        raise ValueError("unsupported cycle schema")
    for name in ("name", "top", "clock"):
        value = document.get(name)
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            raise ValueError(f"{name} must be an identifier")
    seen_names: set[str] = set()
    seen_ports: set[str] = {str(document["clock"])}
    for direction in ("inputs", "outputs"):
        fields = document.get(direction)
        if not isinstance(fields, list) or not fields:
            raise ValueError(f"{direction} must be a non-empty list")
        for field in fields:
            if not isinstance(field, dict):
                raise ValueError(f"invalid {direction} field")
            field_name = field.get("name")
            port = field.get("port")
            kind = field.get("type")
            width = field.get("width")
            if not isinstance(field_name, str) or not IDENTIFIER.fullmatch(field_name):
                raise ValueError(f"invalid field name {field_name!r}")
            if not isinstance(port, str) or not IDENTIFIER.fullmatch(port):
                raise ValueError(f"invalid port name {port!r}")
            if kind not in TYPE_INFO:
                raise ValueError(f"unsupported type {kind!r}")
            if not isinstance(width, int) or isinstance(width, bool):
                raise ValueError(f"{field_name}.width must be an integer")
            if width < 1 or width > TYPE_INFO[kind][2] * 8:
                raise ValueError(
                    f"{field_name}.width={width} does not fit ABI type {kind}"
                )
            if field_name in seen_names:
                raise ValueError(f"duplicate field name {field_name}")
            if port in seen_ports:
                raise ValueError(f"duplicate port binding {port}")
            seen_names.add(field_name)
            seen_ports.add(port)


def validate_verilator_json(document: dict[str, object], path: Path) -> None:
    tree = json.loads(path.read_text(encoding="utf-8"))
    top_name = document["top"]
    top_modules = [
        module
        for module in tree.get("modulesp", [])
        if module.get("type") == "MODULE" and module.get("level") == 1
    ]
    if len(top_modules) != 1 or top_modules[0].get("name") != top_name:
        actual = [module.get("name") for module in top_modules]
        raise ValueError(f"schema top {top_name!r} does not match Verilator top {actual!r}")

    types = {}
    for item in tree.get("miscsp", []):
        if item.get("type") == "TYPETABLE":
            types.update({kind["addr"]: kind for kind in item.get("typesp", [])})

    ports = {
        item["name"]: item
        for item in top_modules[0].get("stmtsp", [])
        if item.get("type") == "VAR" and item.get("isPrimaryIO")
    }
    expected = {
        document["clock"]: {"direction": "INPUT", "width": 1},
    }
    for field in document["inputs"]:
        expected[field["port"]] = {"direction": "OUTPUT", "width": field["width"]}
    for field in document["outputs"]:
        expected[field["port"]] = {"direction": "INPUT", "width": field["width"]}

    if set(ports) != set(expected):
        missing = sorted(set(expected) - set(ports))
        extra = sorted(set(ports) - set(expected))
        raise ValueError(f"cycle schema/top port mismatch: missing={missing}, extra={extra}")

    for name, want in expected.items():
        port = ports[name]
        if port.get("direction") != want["direction"]:
            raise ValueError(
                f"port {name} direction is {port.get('direction')}, expected {want['direction']}"
            )
        dtype = types.get(port.get("dtypep"))
        if not dtype or dtype.get("type") != "BASICDTYPE":
            raise ValueError(f"port {name} has unsupported Verilator dtype")
        if dtype.get("signed"):
            raise ValueError(f"port {name} is signed; cycle ABI fields are unsigned")
        bit_range = dtype.get("range")
        if bit_range is None:
            actual_width = 1
        else:
            match = re.fullmatch(r"(-?\d+):(-?\d+)", bit_range)
            if not match:
                raise ValueError(f"port {name} has unsupported range {bit_range!r}")
            actual_width = abs(int(match.group(1)) - int(match.group(2))) + 1
        if actual_width != want["width"]:
            raise ValueError(
                f"port {name} width is {actual_width}, expected {want['width']}"
            )


def layout(fields: list[dict[str, str]]) -> tuple[int, int, list[int]]:
    size = 0
    alignment = 1
    offsets = []
    for field in fields:
        _, _, field_size, field_align = TYPE_INFO[field["type"]]
        size = (size + field_align - 1) // field_align * field_align
        offsets.append(size)
        size += field_size
        alignment = max(alignment, field_align)
    size = (size + alignment - 1) // alignment * alignment
    return size, alignment, offsets


def rust_source(document: dict[str, object], schema_hash: int) -> str:
    inputs = document["inputs"]
    outputs = document["outputs"]
    input_size, input_align, _ = layout(inputs)
    output_size, output_align, _ = layout(outputs)

    def one_struct(name: str, fields: list[dict[str, str]]) -> str:
        lines = [
            "#[repr(C)]",
            "#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]",
            f"pub struct {name} {{",
        ]
        for field in fields:
            lines.append(f"    pub {field['name']}: {TYPE_INFO[field['type']][0]},")
        lines.append("}")
        return "\n".join(lines)

    return f"""// @generated by sim/generate_cycle_bindings.py; do not edit.

pub const SCHEMA_HASH: u64 = 0x{schema_hash:016x};
pub const INPUT_SIZE: usize = {input_size};
pub const INPUT_ALIGN: usize = {input_align};
pub const OUTPUT_SIZE: usize = {output_size};
pub const OUTPUT_ALIGN: usize = {output_align};

{one_struct('CycleInputs', inputs)}

{one_struct('CycleOutputs', outputs)}

const _: [(); INPUT_SIZE] = [(); ::core::mem::size_of::<CycleInputs>()];
const _: [(); INPUT_ALIGN] = [(); ::core::mem::align_of::<CycleInputs>()];
const _: [(); OUTPUT_SIZE] = [(); ::core::mem::size_of::<CycleOutputs>()];
const _: [(); OUTPUT_ALIGN] = [(); ::core::mem::align_of::<CycleOutputs>()];
"""


def cpp_source(document: dict[str, object], schema_hash: int) -> str:
    inputs = document["inputs"]
    outputs = document["outputs"]
    input_size, input_align, input_offsets = layout(inputs)
    output_size, output_align, output_offsets = layout(outputs)

    def one_struct(name: str, fields: list[dict[str, str]]) -> list[str]:
        lines = [f"struct {name} {{"]
        for field in fields:
            lines.append(f"    {TYPE_INFO[field['type']][1]} {field['name']};")
        lines.append("};")
        return lines

    lines = [
        "// @generated by sim/generate_cycle_bindings.py; do not edit.",
        "#pragma once",
        "",
        '#include "Vrustdv_dut.h"',
        "",
        "#include <cstddef>",
        "#include <cstdint>",
        "",
        "namespace rustdv_cycle_bindings {",
        f"constexpr std::uint64_t kSchemaHash = 0x{schema_hash:016x}ULL;",
        f"constexpr std::uint32_t kInputSize = {input_size};",
        f"constexpr std::uint32_t kInputAlign = {input_align};",
        f"constexpr std::uint32_t kOutputSize = {output_size};",
        f"constexpr std::uint32_t kOutputAlign = {output_align};",
        "",
        *one_struct("CycleInputs", inputs),
        "",
        *one_struct("CycleOutputs", outputs),
        "",
        "inline void capture_inputs(const Vrustdv_dut& dut, CycleInputs& values) {",
    ]
    for field in inputs:
        lines.append(
            f"    values.{field['name']} = static_cast<{TYPE_INFO[field['type']][1]}>(dut.{field['port']});"
        )
    lines.extend(
        ["}", "", "inline void apply_outputs(Vrustdv_dut& dut, const CycleOutputs& values) {"]
    )
    for field in outputs:
        lines.append(f"    dut.{field['port']} = values.{field['name']};")
    lines.extend(
        [
            "}",
            "",
            f"inline void set_clock(Vrustdv_dut& dut, std::uint8_t value) {{ dut.{document['clock']} = value; }}",
            "",
            f"static_assert(sizeof(CycleInputs) == {input_size}, \"CycleInputs size\");",
            f"static_assert(alignof(CycleInputs) == {input_align}, \"CycleInputs align\");",
            f"static_assert(sizeof(CycleOutputs) == {output_size}, \"CycleOutputs size\");",
            f"static_assert(alignof(CycleOutputs) == {output_align}, \"CycleOutputs align\");",
        ]
    )
    for field, offset in zip(inputs, input_offsets):
        lines.append(
            f"static_assert(offsetof(CycleInputs, {field['name']}) == {offset}, \"CycleInputs.{field['name']} offset\");"
        )
    for field, offset in zip(outputs, output_offsets):
        lines.append(
            f"static_assert(offsetof(CycleOutputs, {field['name']}) == {offset}, \"CycleOutputs.{field['name']} offset\");"
        )
    lines.extend(["", "}  // namespace rustdv_cycle_bindings", ""])
    return "\n".join(lines)


def update(path: Path, content: str, check: bool) -> bool:
    current = path.read_text() if path.is_file() else None
    if current == content:
        return True
    if check:
        print(f"stale generated cycle binding: {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"generated {path}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("schema", type=Path)
    parser.add_argument("--rust", type=Path)
    parser.add_argument("--cpp", type=Path)
    parser.add_argument("--verilator-json", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = json.loads(args.schema.read_text(encoding="utf-8"))
    validate(document)
    if not args.rust and not args.cpp and not args.verilator_json:
        parser.error("request generated outputs or --verilator-json validation")
    if args.check and not (args.rust or args.cpp):
        parser.error("--check requires --rust or --cpp")
    if args.verilator_json:
        validate_verilator_json(document, args.verilator_json)
    schema_hash = canonical_hash(document)
    okay = True
    if args.rust:
        okay = update(args.rust, rust_source(document, schema_hash), args.check)
    if args.cpp:
        okay &= update(args.cpp, cpp_source(document, schema_hash), args.check)
    return 0 if okay else 1


if __name__ == "__main__":
    raise SystemExit(main())
