from __future__ import annotations

import ctypes
import json
import sys

from PySide6.QtWidgets import QApplication, QMessageBox
from oem.config import root_path, load_brand, runtime_exe, user_data
from oem.client import Client
from oem.ui import Window


def main():
    root = root_path()
    brand = load_brand(root)
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(brand["product_id"])
        ctypes.windll.kernel32.CreateMutexW.restype = ctypes.c_void_p
        installation_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "CDM_OEM_" + brand["product_id"])
    app = QApplication(sys.argv)
    lock = json.loads((root / "cdm-runtime.lock.json").read_text(encoding="utf-8"))
    data = user_data(brand)
    client = Client(runtime_exe(root), data / "firmware", lock["version"])
    window = Window(client, brand, root, data / "settings.json")
    window.show()
    result = app.exec()
    if sys.platform == "win32" and installation_mutex:
        ctypes.windll.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.CloseHandle(installation_mutex)
    return result


if __name__ == "__main__":
    sys.exit(main())
