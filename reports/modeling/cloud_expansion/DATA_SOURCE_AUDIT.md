# Data source and storage audit

The Figshare API metadata for article **24237376**, version **4**, names the four development files below. Local copies of all four matched both the provider's MD5 and the previously inventoried SHA-256. The raw total is **4,413,747,290 bytes (4.11 GiB)**. The notebook resolves the pinned file URLs from the versioned metadata each time. It downloads only the four allowlisted files. [Pinned Figshare v4 record](https://doi.org/10.6084/m9.figshare.24237376.v4) · [Versioned API metadata](https://api.figshare.com/v2/articles/24237376/versions/4) · [Machine-readable pins](source_manifest.json)

| Year | Filename | Official file ID | Exact bytes | Provider MD5 | Versioned metadata download URL |
| --- | --- | ---: | ---: | --- | --- |
| 2018 | `eaglei_outages_2018.csv` | 42547879 | 999,210,542 | `726543e4a392e220108b035ba4c52e43` | `https://ndownloader.figshare.com/files/42547879` |
| 2019 | `eaglei_outages_2019.csv` | 42547885 | 1,102,778,792 | `0ff77af0106486eb7bdc6c5051bd916a` | `https://ndownloader.figshare.com/files/42547885` |
| 2020 | `eaglei_outages_2020.csv` | 42547894 | 1,170,699,724 | `3b1e76e7ff0445da2b9a2fe4819c0e88` | `https://ndownloader.figshare.com/files/42547894` |
| 2021 | `eaglei_outages_2021.csv` | 42547891 | 1,141,058,232 | `b5a5912be793ca22dddcc73ca2c3379d` | `https://ndownloader.figshare.com/files/42547891` |

The checksum audit streamed existing local bytes. No nationwide source files were downloaded during preparation. The 2022 source contents were never opened or downloaded. The download code checks size before computing both hashes and publishes the final filename only after both hashes pass. The local audit contains full SHA-256 values and artifact digests. [Storage audit JSON](local_storage_audit.json)

## Exact local Parquet payload sizes

These are measured file sizes in bytes for the current verified development datasets. The totals count Parquet payload files and exclude Spark success markers, metadata sidecars, and superseded backup directories.

| Dataset | Parquet files | Rows | Exact bytes |
| --- | ---: | ---: | ---: |
| Windows sample Silver | 1 | 333,631 | 3,759,630 |
| Windows county Silver | 1 | 416,940 | 8,939,849 |
| Windows sample Gold features | 1 | 333,631 | 7,423,245 |
| Windows county Gold features | 1 | 416,940 | 20,620,841 |
| Windows county label audit | 1 | 416,940 | 26,421,067 |
| Pilot Bronze | 175 | 2,583,294 | 11,838,914 |
| Pilot Silver | 80 | 2,557,234 | 36,035,218 |
| Pilot labels | 30 | 2,557,234 | 46,240,430 |
| Pilot augmented history | 9 | 1,635,860 | 49,457,933 |
| Official RF validation predictions | 1 | 102,449 | 1,420,246 |

The audit measured **35,391,336,448 bytes (32.96 GiB)** of free local disk. The longer-history XGBoost champion is 197,050 bytes. The selected official Random Forest is 7,485,761 bytes and its frozen development bundle is 8,081,537 bytes. The audit also records the other experimental models and the three protected notebook hashes. [Existing experiment verification](../local_improvement/REPRODUCE.md)

## Expanded storage and memory estimates

The pilot history file rate is about **30.23 compressed bytes per eligible row**. Holding the 582,532 development rows fixed gives point estimates of 108,312,831 bytes (103 MiB) with 3M training rows and 259,480,819 bytes (247 MiB) with 8M. Compression and partition overhead vary by county and value distribution. Plan for roughly 0.1–0.25 GiB of final eligible features for Tier B and 0.25–0.60 GiB for Tier C. Coverage checkpoints, candidate features, four raw files, OOF outputs, and Spark scratch account for the rest.

| Activity | Planning allowance | Runtime gate |
| --- | --- | --- |
| Drive persistence | 10 GiB free, 15 GiB more comfortable for repeated or larger runs | Source bytes and checkpoint writes must fit the account quota |
| Spark preparation | 7–10 GiB available RAM, 22 GiB scratch free for both data stages in one session | 7 GiB RAM and 15 GiB scratch at stage entry, with 12 GiB minimum scratch at coverage scans |
| Tier A fit | 5–6 GiB available RAM | About 3.77 GiB with 28 encoded inputs, plus 7 GiB scratch |
| Tier B fit | 10–12 GiB available RAM | About 7.55–8.62 GiB at 3M with 44–56 encoded inputs, plus 7 GiB scratch |
| Near-8M Tier C fit | 24–32 GiB available RAM | About 21.9 GiB with 69 encoded inputs, plus 7 GiB scratch |

Available RAM is measured immediately before work, including a cgroup memory limit when detectable. The guard estimates `2.5 GiB + rows × (4 × 8 × encoded width + 400 bytes)`. This is a headroom estimate for Arrow, pandas, preprocessing and XGBoost workspace. Colab allocation and runtime length vary, and more Drive quota does not increase VM scratch space. [Google Colab FAQ](https://research.google.com/colaboratory/faq.html)
