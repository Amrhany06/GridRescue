# Native Spark storage on Windows

## Diagnosis

The Python worker succeeded on a synthetic row. A fresh Spark JVM reported Spark **3.5.3**, Hadoop **3.3.4**, no `winutils.exe`, and `NativeCodeLoader.isNativeCodeLoaded() == false`. `spark.range(5).write.parquet(...)` failed when Hadoop's `FileOutputCommitter` called `RawLocalFileSystem.setPermission`. The stack trace resolved to unset `HADOOP_HOME` and a missing `winutils.exe`. The bundled `hadoop-client-api` and `hadoop-client-runtime` JARs both have version 3.3.4. The baseline log is in the local workspace at `artifacts/windows_native_baseline.log`.

The repaired runtime uses Windows 11 x64, the existing `.venv` with Python **3.12.14**, Eclipse Temurin **17.0.20.1** and PySpark **3.5.3**. The working installations and the Arrow-local backend were retained.

## Source and build verification

The proposed `notepass` 3.3.4 release has an inspectable recipe that checks out the corresponding Apache tag and builds Hadoop Common on a Windows runner. Its release asset has no published digest or signature in GitHub metadata, and no corresponding build run was available through the tag-filtered Actions API. I built from Apache's signed source locally. The community binary ZIP was neither downloaded nor executed. [Community release](https://github.com/notepass/hadoop-native-win-libs/releases/tag/rel%2Frelease-3.3.4), [tagged workflow](https://raw.githubusercontent.com/notepass/hadoop-native-win-libs/rel/release-3.3.4/.github/workflows/build-native-libs.yml).

Downloaded only the 34 MiB Hadoop 3.3.4 source archive, its detached signature and SHA-512 checksum from the Apache archive, and Apache's Hadoop release `KEYS`. The archive SHA-512 matched Apache's published value `d65dc46d83f137909d645f2a410d27d8e9e57b9162d8c431dff3d2c96f5071c1b7817fcc7c7f07e2400fac198bdbebdbe1a1de99fa988e8eb33e1d280d62cf6d`. GnuPG validated the signature by Steve Loughran's Apache release key, fingerprint `38237EE425050285077DB57AD22CF846DBB162A0`, imported from the project `KEYS` over HTTPS. [Apache source release](https://archive.apache.org/dist/hadoop/common/hadoop-3.3.4/), [Apache Hadoop signing keys](https://downloads.apache.org/hadoop/common/KEYS).

The local build used Apache's unchanged Windows projects, the existing Visual Studio 2022 MSVC v143 toolset (14.44.35207), Windows SDK 10.0.22621.0, and `Release|x64`. It built `winutils.sln`, generated JNI headers with Temurin `javac -h` from Hadoop's `NativeIO`, `JniBasedUnixGroupsMapping`, `NativeCrc32` and `NativeCodeLoader` Java sources against PySpark's existing JARs, and built `native.vcxproj` using the resulting headers and `libwinutils.lib`. The workspace retains the source archive, signature log and build logs. `dumpbin` confirmed both installed files are x64 and that `hadoop.dll` exports Windows `NativeIO` access and file-creation methods. [Apache 3.3.4 build instructions](https://github.com/apache/hadoop/blob/rel/release-3.3.4/BUILDING.txt).

Only these two runtime files were installed under `artifacts/windows-native-hadoop/hadoop-3.3.4/bin`.

| File | Bytes | SHA-256 of the installed build |
|---|---:|---|
| `winutils.exe` | 120,320 | `7aea6b168b64366d613345df97087032ccd1a9c539d78b6ad27c6787445af1d6` |
| `hadoop.dll` | 80,896 | `6ad5d53074692eb540c64b20a6ddd3bae9295c8829c26c8d0f3db407257f5c69` |

## Windows configuration

`HADOOP_HOME` is `C:\Users\Amr Hany\Downloads\GridRescue\artifacts\windows-native-hadoop\hadoop-3.3.4`. The installer helper validated both file hashes, set a process environment for the initial smoke test, then persisted the directory and one `bin` entry in Windows user settings. A second invocation confirmed that the original user PATH prefix and registry value type were preserved and no duplicate was added. Windows generated a fresh user environment block and a new PowerShell discovered the expected executable. JVM diagnostics showed `NativeIO` loading the DLL from that same `bin`. This setup uses the current user and existing Java installation. No `-D` override was needed.

Use a new terminal from the Start menu, or close and reopen VS Code or Codex to refresh its inherited environment. A machine reboot is unnecessary. From the GridRescue root, the development-only preflight command is

```powershell
.\.venv\Scripts\python.exe scripts/preflight.py --development-fixtures
```

An existing terminal can start the same command with the verified setup immediately. The `--` separates the configuration options from the child command.

```powershell
.\.venv\Scripts\python.exe scripts/configure_windows_native_spark.py -- .\.venv\Scripts\python.exe scripts/preflight.py --development-fixtures
```

If the project is moved, use `scripts/configure_windows_native_spark.py --persist-user` after moving the installed files with it. Windows PowerShell's script execution policy was left in place. The helper runs through the existing Python environment.

## Verification

| Check | Result |
|---|---|
| Basic native Spark write | `spark.range(5).write.parquet(...)` and readback matched IDs 0 through 4 in a fresh Python process. |
| Native Parquet overwrite | Three synthetic rows including a null value replaced the range. Readback matched all rows and the exact nullable fixture schema. |
| Native Spark ML save and reload | The Imputer, VectorAssembler and StandardScaler were written through Spark, reloaded with `PipelineModel.load`, and returned identical feature vectors. |
| Previously failing test | `test_preparation_fits_only_training_and_saves_reload` passed on its own. One test ran in 46.0 seconds with exit code 0. |
| Full GridRescue suite | `python -m unittest discover -s tests -v` passed all 46 tests in 147.1 seconds with exit code 0. |
| Development-only final-evaluation preflight | Passed in a fresh PowerShell using the saved Windows user environment. Loaded the saved 13-feature Spark preparation and the frozen classifier, reproduced 100 fixture scores and labels exactly, and round-tripped 15 synthetic label-audit rows and one quarantine row through native Spark Parquet. The temporary directory was cleaned and the Spark launcher and JVM exited. |

The smoke, targeted-test, full-suite and fresh-preflight logs are in the local workspace under `artifacts/windows-native-hadoop/`. [Machine-readable preflight](environment.json)

The sandboxed runs emitted a PySpark launcher `taskkill` access-denied diagnostic after the successful tests. In the fresh user-process verification, Windows confirmed Spark child-process cleanup and the command returned exit code 0. The existing Arrow-local path also passed its tests.

Compared 84 pre-existing artifact and source file hashes, including the frozen model, Spark preprocessing, modeling reports, scope datasets and notebooks. They matched the pre-repair snapshot. The four raw development CSVs retained their sizes and modification timestamps. The 2022 holdout remains sealed and the once-only journal remains absent.

The native build covers local filesystem I/O. Optional Hadoop zlib and ISA-L integrations were not compiled or tested. Spark used its existing dependencies for the tested Parquet path. The once-only 2022 evaluator remains separately gated.
