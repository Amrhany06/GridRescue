"""Read-only full-file development integrity audit, excluding held-out 2022.

Run after scripts/preflight.py succeeds. Scans each development year separately,
without cache, deduplication, large collects, feature engineering or labels.
Only a single aggregate row is collected per source. Original CSVs are unchanged.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from functools import reduce
from operator import or_
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def development_sources(root: Path) -> list[Path]:
    sources = []
    for year in range(2018, 2022):
        name = f"eaglei_outages_{year}.csv"
        candidates = [root / "data" / "raw" / name, root / name]
        selected = next((path for path in candidates if path.is_file()), None)
        if selected is None:
            raise FileNotFoundError(f"Missing development source: {name}")
        sources.append(selected)
    return sources


def integrity_summary(raw, source_year: int) -> dict:
    from pyspark.sql import functions as F

    # Same conservative token rules as gridrescue.pipeline.clean. This audit
    # counts invalid flags without materializing/quarantining the full data.
    parsed = raw.withColumn("timestamp", F.expr(
        "try_to_timestamp(run_start_time, 'yyyy-MM-dd HH:mm:ss')"
    )).withColumn("_count", F.expr("try_cast(customers_out as bigint)"))
    conditions = {
        "invalid_fips": ~F.col("fips_code").rlike("^[0-9]{5}$"),
        "invalid_timestamp": F.col("timestamp").isNull() | ~F.col("run_start_time").rlike(
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"),
        "off_grid_timestamp": F.col("timestamp").isNotNull() & (F.unix_timestamp("timestamp") % 900 != 0),
        "invalid_count": ~F.col("customers_out").rlike("^[0-9]+$") | F.col("_count").isNull(),
        "missing_geography": F.col("county").isNull() | F.col("state").isNull(),
    }
    flags = {name: F.coalesce(condition, F.lit(True)) for name, condition in conditions.items()}
    invalid = reduce(or_, flags.values())

    def total(condition):
        return F.coalesce(F.sum(condition.cast("long")), F.lit(0))

    aggregates = [
        F.count("*").alias("parsed_rows"),
        total(invalid).alias("invalid_rows_any_reason"),
        total(~invalid).alias("valid_rows_before_deduplication"),
        F.min("timestamp").cast('string').alias("min_parsed_timestamp_utc"),
        F.max("timestamp").cast('string').alias("max_parsed_timestamp_utc"),
        total(F.year("timestamp") != source_year).alias("parsed_timestamp_outside_source_year"),
    ]
    aggregates.extend(total(F.col(column).isNull()).alias("null_" + column) for column in raw.columns)
    aggregates.extend(total(flag).alias(name) for name, flag in flags.items())
    summary = parsed.agg(*aggregates).first().asDict()
    assert summary["parsed_rows"] == summary["invalid_rows_any_reason"] + summary["valid_rows_before_deduplication"]
    return summary


def write_report(path: Path, report: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    paths = development_sources(root)
    sys.path.insert(0, str(ROOT / "src"))
    from gridrescue.pipeline import make_spark, read_source

    report_path = root / "reports" / "full_development_audit.json"
    report_path.parent.mkdir(exist_ok=True)
    report = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Complete local development CSVs 2018-2021 only; 2022 not read",
        "status": "RUNNING", "files": [],
        "semantics": {
            "parsed_rows": "Spark CSV FAILFAST parser rows, excluding source header",
            "invalid_flags": "Reason flags may overlap; invalid_rows_any_reason counts each row once",
            "source_year_check": "Reported separately; does not silently amend shared cleaning rules",
            "timestamp_timezone": "UTC interpretation follows project documentation, not source-string timezone proof",
            "not_measured": ["exact duplicates", "conflicting county-time keys", "gaps", "Silver rows", "features", "labels", "model metrics"],
        },
    }
    write_report(report_path, report)
    spark = None
    try:
        spark = make_spark("GridRescue-full-development-integrity")
        # Preflight is a separate command; no system configuration is changed.
        for path in paths:
            started = time.perf_counter()
            year = int(path.stem.rsplit("_", 1)[1])
            if year not in range(2018, 2022):
                raise ValueError("Held-out or unsupported source blocked")
            summary = integrity_summary(read_source(spark, [path]), year)
            measured = {
                "source": str(path.relative_to(root)), "year": year,
                "source_bytes": path.stat().st_size, **summary,
                "elapsed_seconds": time.perf_counter() - started,
                "completed_utc": datetime.now(timezone.utc).isoformat(),
            }
            report["files"].append(measured)
            report["parsed_development_rows_so_far"] = sum(item["parsed_rows"] for item in report["files"])
            write_report(report_path, report)
            with (root / "reports" / "full_development_audit_log.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps(measured, default=str) + "\n")
            print(json.dumps(measured, default=str), flush=True)
        report["status"] = "VERIFIED_FULL_DEVELOPMENT_INTEGRITY_ONLY"
        report["completed_utc"] = datetime.now(timezone.utc).isoformat()
        write_report(report_path, report)
        return 0
    except Exception as error:
        report.update(status="FAILED", error=repr(error))
        write_report(report_path, report)
        raise
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
