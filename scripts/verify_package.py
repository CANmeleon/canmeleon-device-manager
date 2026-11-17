from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from prepare_runtime import check_runtime


def verify(package: Path):
    package = package.resolve()
    for name in ('CDM_OEM.exe','oem/branding.json','cdm-runtime.lock.json','LICENSE','THIRD_PARTY_NOTICES.md'):
        if not (package/name).is_file():
            raise ValueError(f'Missing package file: {name}')
    prohibited = [p for p in package.rglob('*') if p.suffix.lower() in ('.py','.pyc','.pyo')]
    if prohibited:
        raise ValueError(f'Python source/bytecode in runtime package: {prohibited[0]}')
    lock = json.loads((package/'cdm-runtime.lock.json').read_text(encoding='utf-8'))
    check_runtime(package/'runtime/cdm/CANmeleon-device-manager.exe', lock)
    print(f'Package verified: {package}')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--package',required=True,type=Path)
    verify(parser.parse_args().package)
