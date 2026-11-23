"""Apply Apache SPARK-53759's small socket-close backport to local PySpark 3.5.3.

Upstream: https://github.com/apache/spark/pull/55225
Only the project's ignored .venv is modified, with an original backup and hashes.
Remove this workaround when upgrading to a release containing the upstream fix.
"""
import hashlib
import importlib.metadata
import json
import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.name != 'nt':
        print('Windows worker backport unnecessary on this platform.')
        return
    import pyspark
    if importlib.metadata.version('pyspark') != '3.5.3':
        raise RuntimeError('Review worker backport before using a different Spark version.')
    path = Path(pyspark.__file__).parent / 'worker.py'
    if not path.resolve().is_relative_to((ROOT / '.venv').resolve()):
        raise RuntimeError('Refusing to modify a non-project Python installation')
    original = path.read_bytes()
    old = b'    main(sock_file, sock_file)\n'
    new = b'    try:\n        main(sock_file, sock_file)\n    finally:\n        sock_file.close()\n'
    if not original.endswith((old,new)):
        raise RuntimeError('Unexpected worker source; no patch applied')
    backup = ROOT / 'artifacts/runtime_patch/pyspark_worker_original.py'
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        backup.write_bytes(original)
    patched = original if original.endswith(new) else original[:-len(old)] + new
    if patched != original:
        path.write_bytes(patched)
    # Spark workers import pyspark.zip ahead of site-packages; patch the same
    # source there as well. Changing only worker.py leaves the actual worker old.
    archive = path.parent / 'python/lib/pyspark.zip'
    archive_backup = backup.parent / 'pyspark_original.zip'
    if not archive_backup.exists():
        shutil.copy2(archive, archive_backup)
    with zipfile.ZipFile(archive) as source:
        zipped = source.read('pyspark/worker.py')
        if not zipped.endswith((old,new)):
            raise RuntimeError('Unexpected archived worker source')
        if zipped.endswith(old):
            temporary = archive.with_suffix('.zip.tmp')
            with zipfile.ZipFile(temporary,'w') as target:
                for entry in source.infolist():
                    payload = source.read(entry.filename)
                    if entry.filename == 'pyspark/worker.py':
                        payload = payload[:-len(old)] + new
                    target.writestr(entry,payload)
        else:
            temporary = None
    if temporary is not None:
        temporary.replace(archive)
    report = {'issue': 'SPARK-53759', 'upstream': 'https://github.com/apache/spark/pull/55225',
              'package': 'pyspark==3.5.3', 'scope': '.venv only; explicit close flushes buffered worker results',
              'before_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(), 'after_sha256': hashlib.sha256(patched).hexdigest(),
              'worker_archive_patched':True,'original_archive_sha256':hashlib.sha256(archive_backup.read_bytes()).hexdigest(),
              'patched_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
    (ROOT / 'reports/spark_worker_backport.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Applied upstream socket-close backport; original and hashes saved.')


if __name__ == '__main__':
    main()
