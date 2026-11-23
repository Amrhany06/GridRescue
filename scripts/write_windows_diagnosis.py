"""Write factual Windows recovery evidence after successful strict verification."""
import json
import re
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(path): return json.loads((ROOT/path).read_text(encoding='utf-8'))

def main():
    proof=read('reports/persistence_validation.json')
    assert proof['status']=='VERIFIED' and proof['storage_backend']=='arrow-local'
    probes=read('reports/windows_spark_probes.json')
    audits={scope:read(f'reports/windows/{scope}/audit.json') for scope in ['sample','county']}
    tests=(ROOT/'reports/verification/tests.txt').read_text(encoding='utf-8')
    count=int(re.findall(r'Ran (\d+) tests',tests)[-1])
    errors=re.findall(r'^ERROR: (test_\w+)',tests,re.MULTILINE)
    assert errors==['test_preparation_fits_only_training_and_saves_reload']
    rows=[]; exports=[]
    for scope,audit in audits.items():
        values=audit['counts']; prepared=proof['scopes'][scope]
        rows.append(f"| {scope} | {values['raw']:,} | {values['invalid']:,} | {values['exact_duplicates_removed']:,} | {values['conflict_rows']:,} | {values['silver']:,} | {prepared['rows']:,} | {prepared['exact_vector_mismatches']} |")
        for stage,path in [('bronze',ROOT/'data/windows/bronze'/scope),('gold',ROOT/'data/windows/gold'/scope/'features'),('prepared',ROOT/'artifacts/windows'/scope/'prepared_features')]:
            metadata=json.loads((path/'_gridrescue_storage.json').read_text())
            exports.append(f"| {scope}/{stage} | {metadata['rows']:,} | {metadata['spark_partitions']} | {metadata['largest_export_partition_rows']:,} | {metadata['arrow_batch_rows']:,} | {metadata['python_rss_sampled_peak_bytes']/1024**2:.1f} |")
    text=f'''# Native Windows Spark diagnosis and storage outcome

Verified at {datetime.now(timezone.utc).isoformat()}. **Outcome: Arrow-local storage is VERIFIED for the two bounded development cohorts. Hadoop's native Windows writer remains BLOCKED. This is a storage workaround, not a repair of Hadoop filesystem support. Task 3 is PAUSED for user review; 2022 remains sealed from features, labels, fitting, tuning and scoring.**

## Original failure and verified cause

The minimal reproduction is `scripts/diagnose_windows_spark.py`. Its complete exceptions and settings are retained in `reports/windows_spark_probes.json` and `.txt`; the original `environment.json`, previous reports and native test logs are preserved.

`DataFrame.write.parquet(...)` and `PipelineModel.write().save(...)` fail with:

```text
java.lang.RuntimeException: java.io.FileNotFoundException:
HADOOP_HOME and hadoop.home.dir are unset.
org.apache.hadoop.util.Shell.getWinUtilsPath
org.apache.hadoop.fs.RawLocalFileSystem.setPermission
```

The actual boundary is Hadoop local filesystem directory/file permission setup during output commit. Native Hadoop is not loaded, and its Windows command fallback cannot resolve winutils. This is distinct from Python imports, Spark execution, Parquet encoding and Java compatibility. A synthetic Spark filter/aggregation returned the independently expected sum 1,140, while both native saves failed. Spark itself successfully read Arrow-written Parquet and verified its contents.

## Installed state and compatibility

- Windows Python: `{probes['python'].splitlines()[0]}`.
- PySpark: `{probes['versions']['pyspark']}`; bundled Hadoop runtime: `{probes['hadoop_version']}`.
- Java runtime: `{probes['java_runtime']}`; `JAVA_HOME` resolves to the installed Temurin JDK 17.
- setuptools: `{probes['versions']['setuptools']}`; installed PyArrow: `{probes['versions']['pyarrow']}`. No Windows environment reinstall was performed.
- `HADOOP_HOME` and JVM `hadoop.home.dir`: unset. Native Hadoop loaded: `{probes['native_hadoop_loaded']}`. Local filesystem wrapper: `{probes['filesystem_class']}`.
- Java 17 is supported by Spark 3.5.x. Python 3.12/Windows already has the documented project-local SPARK-53759 worker backport; its previous backups/evidence remain. setuptools supplies the distutils compatibility needed by pyspark.ml. Actual fitted Spark preprocessing ran, so this is stronger evidence than imports alone.
- The launcher can print a misleading missing-Python message because its installed `find-spark-home.cmd` checks an unquoted executable path containing spaces. The executable exists, the fallback resolves the pip-installed Spark directory, and workers execute. This warning did not cause the reproduced Hadoop write error.
- Some logs retain PySpark socket ResourceWarnings and an `Access denied` message from the Windows JVM tree-kill cleanup hook (`pyspark/java_gateway.py`). They were not suppressed. Successful Spark jobs and subprocess outcomes are recorded separately; no claim is made that these upstream cleanup warnings were repaired.

## Approaches examined and actual tests

1. Reproduced the unchanged native DataFrame and preprocessing saves; both fail at the permission boundary. An empty/fabricated HADOOP_HOME cannot supply the missing executable/native implementation. No dummy executable, filesystem permission bypass, system-file edit, unofficial binary or global Hadoop patch was used.
2. Confirmed that the installed Arrow writer can create genuine Parquet that Spark reads. Added an explicit `arrow-local` backend alongside `native`; the native integration test is retained unchanged, including its native PipelineModel loader.
3. Initial small tests passed, then strict complete-county comparison caught **48 shifted UTC timestamps**, with all numeric columns matching. The cause was a naive Python datetime round-trip while restoring exact Spark schema/nullability at historical Windows-local clock transitions. `reports/storage_mismatch_diagnosis.json` contains bounded actual examples. The regression failed on four synthetic historical timestamps before the correction (`storage_timestamp_red.txt`). UTC epoch microseconds now cross both Python boundaries; Spark restores timestamp values in the JVM. Exact checks were rerun successfully; no tolerance or assertion was relaxed.
4. One broader test run encountered an intermittent Windows denial while renaming a closed staging directory. Added a bounded retry of only the rename operation and rollback to the previous output on permanent failure. Both failure-path tests passed; data content mismatches still raise immediately. The external process causing the original denial was not identified.
5. Completed full real-cohort write/read checks, then a separate Python process reloaded saved preprocessing and compared every eligible vector, training median, mean, sample standard deviation and feature position. Rows with missing lag history are explicitly exercised. No classifier or 2022 observation was used.

## Real-data reconciliation and reload

| Scope | Parsed rows | Invalid | Exact duplicate removals | Conflict variants | Silver/Gold | Prepared rows | Vector mismatches |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

Each cohort has **seven** exact content round-trips: Bronze, quarantine, Silver, gap summary, Gold features, label audit and prepared features. Bidirectional Spark `exceptAll` verifies full multisets, including nulls, timestamps, every numeric value and row multiplicities. Spark schema equality includes type, column order, nullability and metadata. No sorting is used to conceal mismatches; row order is not a DataFrame guarantee. Separate feature-order assertions protect the thirteen positions in X.

Fresh-process evidence is `reports/persistence_validation.json`: both scopes have zero vector mismatches, zero nonfinite vectors and zero dimension errors; fitted statistics equal those recorded directly from the original in-memory Spark fit. Full per-column null counts and exact comparison results are retained there and in `reports/windows/{{sample,county}}/audit.json`. Failed attempts remain in verification history and `audit_failed.json`, rather than being discarded.

## Memory and scale limits

`storage.write_frame` rejects inputs above **500,000 rows**, redistributes the accepted cohort into **eight round-robin Spark export partitions**, streams `toLocalIterator(prefetchPartitions=False)`, and writes batches of at most **8,192 Arrow rows**. It never calls collect/toPandas on a large DataFrame. SQL aggregations and exact comparisons stay in Spark. Schema restoration uses distributed Spark RDD row streaming, with timestamps kept as integers through Python. Only bounded examples or compact scalar summaries reach the driver.

| Export | Rows | Export partitions | Largest observed partition | Arrow batch limit | Sampled Python RSS MiB |
|---|---|---|---|---|---|
{chr(10).join(exports)}

Spark's iterator may buffer its largest partition. The row cap, eight partitions and measured partition sizes bound this local use; sampled Python RSS excludes JVM memory and is not an absolute peak measurement. The driver writes one local Parquet file per output: this is **not** a scalable distributed writer for the 96-million-row development population. Larger exports require the retained Linux/native backend or separately reviewed infrastructure. No national persistence/performance claim follows from these subset checks.

## Saved preprocessing contract

`artifacts/windows/<scope>/preparation/preparation.json` stores the actual fitted imputation medians, ordered input/output columns, stage UIDs, assembler policy, scaler means/sample standard deviations and settings. `storage.load_preparation` reconstructs genuine Spark ImputerModel, VectorAssembler and StandardScalerModel stages without refitting. It explicitly requires verified Spark **3.5.3** constructors; upgrades need revalidation. This is an intentionally narrow project format, not Spark's native ML directory format and not a general arbitrary-model serializer. Use `load_preparation`, not `PipelineModel.load`, for this format. Only project-generated manifests/artifacts are supported.

## Tests, remaining blocker and Linux fallback

The latest complete suite ran **{count} tests: {count-1} passed, one native integration error**. The sole error is `test_preparation_fits_only_training_and_saves_reload`, with the original Hadoop error above. The original test's AST is checked against the pre-recovery checkpoint by `scripts/review_task12.py`; it was not weakened, skipped or redirected. The seven storage/commit tests cover exact values, UTC transitions, schema/metadata/nullability, null handling, fitted statistics, feature vectors, corruption rejection, row-budget rejection and commit recovery. See `reports/verification/tests.txt`.

Ubuntu/WSL and `.venv-linux` remain installed and preserved. The previously authorized Linux dependency installation completed naturally. Linux-native Parquet and ML persistence have not been newly verified in this recovery task and are not claimed fixed. A matching official Hadoop Windows source build would require a larger toolchain review; no such installation was attempted. Unverified third-party Windows binaries remain excluded.

## Reproduction and review boundary

From the project root, use the existing Windows `.venv/Scripts/python.exe`:

```powershell
.venv/Scripts/python.exe scripts/diagnose_windows_spark.py
.venv/Scripts/python.exe scripts/run_pipeline.py --scope sample --storage arrow-local
.venv/Scripts/python.exe scripts/run_pipeline.py --scope county --storage arrow-local
.venv/Scripts/python.exe scripts/verify_persistence.py --storage arrow-local
.venv/Scripts/python.exe scripts/verify.py tests
```

The native diagnosis and full suite intentionally continue to expose native failure; they are not expected to turn green without a separate safe native solution. Pipeline stages are in `data/windows/`, preprocessing/prepared vectors in `artifacts/windows/`, and measured reports in `reports/windows/`. Prior paths and results are retained. Task 3's native-input training entrypoint has not been repointed or executed; any later integration awaits user review and revised requirements. No WSL removal or reboot was performed.

Primary references: [Spark 3.5.3 installation](https://downloads.apache.org/spark/docs/3.5.3/api/python/getting_started/install.html), [Hadoop RawLocalFileSystem source](https://github.com/apache/hadoop/blob/rel/release-3.3.4/hadoop-common-project/hadoop-common/src/main/java/org/apache/hadoop/fs/RawLocalFileSystem.java), [Spark Imputer source](https://github.com/apache/spark/blob/v3.5.3/mllib/src/main/scala/org/apache/spark/ml/feature/Imputer.scala), [Spark iterator memory contract](https://spark.apache.org/docs/3.5.3/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.toLocalIterator.html).
'''
    (ROOT/'reports/WINDOWS_SPARK_DIAGNOSIS.md').write_text(text,encoding='utf-8')
    print('Wrote factual Windows diagnosis; native failure remains explicit.')

if __name__=='__main__': main()
