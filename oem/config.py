from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def root_path() -> Path:
    if "__compiled__" in globals():
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent.parent


def load_brand(root: Path) -> dict:
    value = json.loads((root / "oem" / "branding.json").read_text(encoding="utf-8"))
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]+", value["product_id"]):
        raise ValueError("Invalid product_id")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value["theme_color"]):
        raise ValueError("Invalid theme_color")
    if not value["pages"] or any(p not in ("devices", "firmware", "help") for p in value["pages"]):
        raise ValueError("Invalid pages")
    for field in ("logo", "icon"):
        path = (root / "oem" / value[field]).resolve()
        if not path.is_relative_to((root / "oem").resolve()):
            raise ValueError("Brand asset must be inside oem/")
    return value


def runtime_exe(root: Path) -> Path:
    base = root / "runtime" / "cdm"
    if not base.exists():
        base = root / ".runtime" / "cdm"
    return base / "CANmeleon-device-manager.exe"


def user_data(brand: dict) -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / brand["product_id"]
    root.mkdir(parents=True, exist_ok=True)
    return root
