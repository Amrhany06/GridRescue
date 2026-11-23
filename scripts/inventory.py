"""Measure source-file bytes, SHA256 and physical lines without parsing labels.

Physical data lines exclude the first (header) line. They are deliberately
separate from parser-level row counts, which the Spark pipeline must measure.
Original manifest headers and examples are preserved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path


def scan_file(path: Path) -> dict:
    started = time.perf_counter()
    digest = hashlib.sha256()
    byte_count = newlines = quotes = 0
    final_byte = b""
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
            newlines += chunk.count(b"\n")
            quotes += chunk.count(b'"')
            final_byte = chunk[-1:]
    physical_lines = newlines + int(bool(byte_count) and final_byte != b"\n")
    return {
        "bytes": byte_count,
        "sha256": digest.hexdigest(),
        "physical_lines_including_header": physical_lines,
        "physical_data_lines": max(physical_lines - 1, 0),
        "newline_bytes": newlines,
        "double_quote_bytes": quotes,
        "ends_with_newline": final_byte == b"\n",
        "scan_seconds": round(time.perf_counter() - started, 6),
        "scan_completed_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": None,
        "status": "BYTES_HASH_PHYSICAL_LINES_VERIFIED; Spark parsed row count pending",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = root / "reports" / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    log_path = root / "reports" / "inventory_log.jsonl"
    for item in manifest["files"]:
        path = root / item["path"]
        measurement = scan_file(path)
        item.update(measurement)
        # Record after each completed file, so an interrupted inventory remains
        # honest about which files were actually measured.
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        with log_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps({"path": item["path"], **measurement}) + "\n")
        print(json.dumps({"path": item["path"], **measurement}), flush=True)
    manifest["physical_data_line_total"] = sum(f["physical_data_lines"] for f in manifest["files"])
    manifest["parsed_row_total"] = None
    manifest["inventory_note"] = (
        "Physical lines and SHA256 measured over every local byte. Parser-level "
        "row counts, malformed records and data quality require separate Spark audit. "
        "2022 received file-integrity inventory only; no label or predictive analysis."
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
