"""Versioned source retrieval, resource gates, and restart-safe cloud checkpoints."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile, ZIP_STORED

import psutil
import requests

YEARS = (2018, 2019, 2020, 2021)
ARTIFACT_MANIFEST = 'checkpoint.json'
GIB = 2**30
CHUNK = 8 * 2**20


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def file_digests(path):
    md5 = hashlib.md5(usedforsecurity=False)
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(CHUNK):
            md5.update(chunk)
            sha.update(chunk)
    return {'size': path.stat().st_size, 'md5': md5.hexdigest(), 'sha256': sha.hexdigest()}


def verify_file(path, expected):
    if path.stat().st_size != expected['size']:
        raise ValueError(f'Incomplete size for {path}: {path.stat().st_size:,} of {expected["size"]:,} bytes')
    actual = file_digests(path)
    if any(actual[k] != expected[k] for k in ('md5', 'sha256')):
        raise ValueError(f'File checksum mismatch for {path}. Preserve or remove that file before retrying.')
    return actual


def inspect_source(metadata, pins):
    """Project only the four pinned entries from the public article metadata."""
    if (metadata.get('id'), metadata.get('version')) != (pins['article_id'], pins['version']):
        raise ValueError('Figshare article or version differs from the source manifest')
    if tuple(row['year'] for row in pins['files']) != YEARS:
        raise ValueError('Only the expected four development years are allowed')
    result = {}
    for pin in pins['files']:
        name = f'eaglei_outages_{pin["year"]}.csv'
        if pin['name'] != name:
            raise ValueError(f'Unexpected pinned filename: {pin["name"]}')
        files = [item for item in metadata['files'] if item.get('name') == name]
        if len(files) != 1:
            raise ValueError(f'Expected exactly one versioned file named {name}')
        item = files[0]
        if (item.get('id'), item.get('size'), item.get('computed_md5')) != (pin['id'], pin['size'], pin['md5']):
            raise ValueError(f'Figshare file metadata differs for {name}')
        if item.get('supplied_md5', pin['md5']) != pin['md5'] or item.get('is_link_only', False):
            raise ValueError(f'Figshare file checksum or hosting differs for {name}')
        url = item.get('download_url', item.get('downloadUrl', ''))
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc not in {'figshare.com', 'ndownloader.figshare.com'}
                or parsed.path not in {f'/files/{pin["id"]}', f'/ndownloader/files/{pin["id"]}'}):
            raise ValueError(f'Unexpected Figshare download link for {name}')
        result[pin['year']] = {**pin, 'download_url': url}
    return result


def fetch_metadata(pins):
    endpoint = f'https://api.figshare.com/v2/articles/{pins["article_id"]}/versions/{pins["version"]}'
    response = requests.get(endpoint, timeout=(15, 45))
    response.raise_for_status()
    return inspect_source(response.json(), pins)


def download_file(url, target, expected, get=requests.get):
    """Write or resume one file. A final name always implies a checksum pass."""
    if target.exists():
        return verify_file(target, expected)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + '.partial')
    offset = partial.stat().st_size if partial.exists() else 0
    total = expected['size']
    if offset > total:
        raise ValueError(f'Partial download exceeds pinned size: {partial}')
    headers = {'Accept-Encoding': 'identity'}
    if offset:
        headers['Range'] = f'bytes={offset}-'
    if offset < total:
        with get(url, headers=headers, stream=True, timeout=(20, 60)) as response:
            response.raise_for_status()
            if response.status_code == 206:
                content_range = response.headers.get('Content-Range', '')
                if content_range != f'bytes {offset}-{total - 1}/{total}':
                    raise ValueError(f'Unexpected Content-Range for {target.name}: {content_range}')
            elif response.status_code == 200:
                offset = 0  # Server ignored Range. Replace the partial from byte zero.
            else:
                raise ValueError(f'Unexpected HTTP status for {target.name}: {response.status_code}')
            with partial.open('ab' if offset else 'wb') as out:
                for chunk in response.iter_content(chunk_size=CHUNK):
                    offset += len(chunk)
                    if offset > total:
                        raise ValueError(f'Response exceeded pinned size for {target.name}')
                    out.write(chunk)
    verified = verify_file(partial, expected)
    os.replace(partial, target)
    return verified


def stage_file(source, target, pin):
    """Copy a checked cloud object to VM scratch and verify the scratch copy."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        tmp = target.with_suffix(target.suffix + '.partial')
        shutil.copyfile(source, tmp)
        verify_file(tmp, pin)
        os.replace(tmp, target)
    else:
        verify_file(target, pin)
    return target


def validate_training_counties(counties, withheld):
    codes = set(counties)
    if (len(codes) != len(counties) or codes & set(withheld)
            or any(not re.fullmatch(r'[0-9]{5}', code) or code.startswith('36') for code in codes)):
        raise ValueError('Training counties contain duplicate, malformed, held-out, or New York FIPS')


def select_tiers(baseline_counts, ranked, withheld):
    """Use whole county prefixes. Only eligible counts determine the tier sizes."""
    baseline = list(baseline_counts)
    ordered = baseline + [code for code, _ in ranked]
    validate_training_counties(ordered, withheld)
    counts = dict(baseline_counts)
    counts.update(ranked)
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError('Invalid eligible row count')
    base_rows = sum(baseline_counts.values())
    totals = [(base_rows, baseline)]
    for code, count in ranked:
        if not count:
            continue
        n, chosen = totals[-1]
        if n + count > 8_000_000:
            break
        totals.append((n + count, [*chosen, code]))
    b = min(totals, key=lambda item: (abs(item[0] - 3_000_000), item[0]))
    return {key: {'rows': n, 'counties': codes} for key, (n, codes) in zip('ABC', (totals[0], b, totals[-1]), strict=True)}


def resources(path):
    available = psutil.virtual_memory().available
    # Colab can use a cgroup with a lower limit than the host's free memory.
    limit, usage = (Path('/sys/fs/cgroup') / name for name in ('memory.max', 'memory.current'))
    if limit.is_file() and usage.is_file():
        value = limit.read_text().strip()
        if value.isdigit():
            available = min(available, max(0, int(value) - int(usage.read_text().strip())))
    return {'CPU threads': os.cpu_count(), 'available RAM GiB': round(available / GIB, 3),
            'total RAM GiB': round(psutil.virtual_memory().total / GIB, 3),
            'free scratch disk GiB': round(shutil.disk_usage(path).free / GIB, 3)}


def require_resources(path, ram, disk, stage):
    capacity = resources(path)
    if capacity['available RAM GiB'] < ram or capacity['free scratch disk GiB'] < disk:
        raise RuntimeError(f'{stage} requires {ram:.1f} GiB available RAM and {disk:.1f} GiB free scratch. '
                           f'Measured {capacity}. Use a larger runtime or keep the smaller tier.')
    print(f'{stage} resources: {capacity}', flush=True)


def gpu_details():
    try:
        return subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                                       text=True, timeout=10).strip()
    except (OSError, subprocess.SubprocessError):
        return 'No visible NVIDIA GPU'


def _records(path):
    return {item.relative_to(path).as_posix(): digest(item) for item in sorted(path.rglob('*'))
            if item.is_file() and item.name != ARTIFACT_MANIFEST}


def _verify_checkpoint(path, stage, expected=None):
    manifest = load(path / ARTIFACT_MANIFEST)
    if manifest['stage'] != stage or (expected is not None and manifest != expected) or manifest['sha256'] != _records(path):
        raise ValueError(f'Checkpoint checksum or stage mismatch: {path}')
    return manifest


def checkpoint(vm, drive, stage, build):
    """Build in scratch, atomically publish one archive, and restore only verified contents."""
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', stage):
        raise ValueError('Invalid checkpoint name')
    vm.mkdir(parents=True, exist_ok=True)
    drive.mkdir(parents=True, exist_ok=True)
    local, archive = vm / stage, drive / f'{stage}.zip'
    stamp = archive.with_suffix('.sha256')
    if archive.exists() and stamp.exists() and stamp.read_text(encoding='ascii').strip() != digest(archive):
        raise ValueError(f'Checkpoint archive checksum mismatch: {archive}')
    with tempfile.TemporaryDirectory(prefix=f'{stage}-', dir=vm) as temp:
        staging = Path(temp)
        if archive.exists():
            if local.exists() and stamp.exists():
                with ZipFile(archive) as packed:
                    expected = json.loads(packed.read(ARTIFACT_MANIFEST))
                _verify_checkpoint(local, stage, expected)
                return local
            try:
                with ZipFile(archive) as packed:
                    for name in packed.namelist():
                        rel = PurePosixPath(name)
                        if rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name:
                            raise ValueError(f'Invalid archive member: {name}')
                    packed.extractall(staging)
            except BadZipFile as exc:
                raise ValueError(f'Checkpoint archive checksum or ZIP validation failed: {archive}') from exc
            expected = _verify_checkpoint(staging, stage)
            if local.exists():
                _verify_checkpoint(local, stage, expected)
            else:
                staging.rename(local)
        else:
            if local.exists():
                _verify_checkpoint(local, stage)
            else:
                build(staging)
                records = _records(staging)
                if not records:
                    raise ValueError(f'Empty checkpoint: {stage}')
                save(staging / ARTIFACT_MANIFEST, {'stage': stage, 'sha256': records})
                staging.rename(local)
            temporary = archive.with_suffix('.zip.partial')
            with ZipFile(temporary, 'w', compression=ZIP_STORED, allowZip64=True) as packed:
                for file in sorted(local.rglob('*')):
                    if file.is_file():
                        packed.write(file, file.relative_to(local).as_posix())
            os.replace(temporary, archive)
        temp_stamp = stamp.with_suffix('.sha256.partial')
        temp_stamp.write_text(digest(archive) + '\n', encoding='ascii')
        os.replace(temp_stamp, stamp)
        return local
