"""Download, verify and stage the exact public CDM runtime. No private imports."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent


def verify_archive(path: Path, lock: dict):
    if path.stat().st_size != lock["size"]:
        raise ValueError("CDM archive size mismatch")
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual.lower() != lock["sha256"].lower():
        raise ValueError("CDM archive SHA-256 mismatch")


def safe_extract(path: Path, destination: Path):
    destination = destination.resolve()
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > 20000 or sum(f.file_size for f in archive.infolist()) > 2 * 1024**3:
            raise ValueError("Archive exceeds runtime limits")
        for entry in archive.infolist():
            name = entry.filename.replace('\\', '/')
            parts = PurePosixPath(name).parts
            target = (destination / name).resolve()
            if (not target.is_relative_to(destination) or name.startswith('/') or ':' in name
                    or '..' in parts or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError("Unsafe archive path")
        archive.extractall(destination)


def check_runtime(exe: Path, lock: dict):
    run = subprocess.run([str(exe), 'version', '--json'], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8',
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=60)
    result = json.loads(run.stdout)
    if (run.returncode or not result.get('ok') or result.get('schema_version') != lock['cli_schema']
            or result.get('data', {}).get('version') != lock['version']
            or result.get('data', {}).get('cli_schema_version') != lock['cli_schema']):
        raise ValueError('CDM runtime version/schema mismatch')


def acquire(lock, archive=None, root=ROOT):
    if not isinstance(lock['size'], int) or lock['size'] <= 0 or len(lock['sha256']) != 64:
        raise ValueError('Runtime lock is not finalized')
    if archive:
        path = Path(archive).resolve()
        verify_archive(path, lock)
        return path
    cache = root / '.cache'
    cache.mkdir(exist_ok=True)
    path = cache / f"cdm-{lock['version']}.zip"
    if path.exists():
        try:
            verify_archive(path, lock)
            return path
        except ValueError:
            pass
    errors = []
    for url in lock['urls']:
        if not url.startswith('https://') or f"/download/{lock['tag']}/" not in url:
            raise ValueError('Runtime URL must be HTTPS and pinned to its release tag')
        partial = path.with_suffix('.partial')
        try:
            with urllib.request.urlopen(url, timeout=90) as response, partial.open('wb') as output:
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > lock['size']:
                        raise ValueError('Download exceeds expected size')
                    output.write(block)
            verify_archive(partial, lock)
            partial.replace(path)
            return path
        except Exception as exc:
            errors.append(f'{url}: {exc}')
        finally:
            partial.unlink(missing_ok=True)
    raise RuntimeError('\n'.join(errors))


def prepare(archive=None, root=ROOT):
    lock = json.loads((root / 'cdm-runtime.lock.json').read_text(encoding='utf-8'))
    path = acquire(lock, archive, root)
    runtime = (root / '.runtime').resolve()
    runtime.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='verified-', dir=runtime) as temporary:
        staged = Path(temporary)
        safe_extract(path, staged)
        matches = list(staged.rglob('CANmeleon-device-manager.exe'))
        if len(matches) != 1:
            raise ValueError('Expected exactly one CDM executable')
        check_runtime(matches[0], lock)
        target = runtime / 'cdm'
        backup = runtime / 'previous'
        for candidate in (target, backup):
            if candidate.is_symlink() or not candidate.resolve().is_relative_to(runtime):
                raise ValueError('Unsafe runtime directory')
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            target.rename(backup)
        try:
            shutil.move(str(matches[0].parent), str(target))
        except Exception:
            if backup.exists() and not target.exists():
                backup.rename(target)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    print(f"CDM {lock['version']} verified: {target}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path)
    prepare(parser.parse_args().archive)
