"""Small adapter for CDM CLI schema 1. No device protocol or private imports."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


from .vector_target import matches_vector_port, present_vector_nodes


class CliError(RuntimeError):
    def __init__(self, code: str, message: str, operation_id=None):
        super().__init__(message)
        self.code, self.operation_id = code, operation_id


def parse_result(stdout: str, exit_code: int, writing=False, expected_completion="verified") -> dict:
    try:
        result = json.loads(stdout)
        valid = (isinstance(result, dict) and type(result.get("schema_version")) is int and result.get("schema_version") == 1
                 and type(result.get("ok")) is bool)
        if valid and not result["ok"]:
            valid = isinstance(result.get("error"), dict) and isinstance(result["error"].get("code"), str)
        if not valid:
            raise ValueError("Unsupported CLI result")
    except (ValueError, TypeError) as exc:
        raise CliError("OUTCOME_UNKNOWN" if writing else "INVALID_RESPONSE",
                       "The backend did not return a valid schema 1 result.") from exc
    if not result["ok"]:
        error = result.get("error") or {}
        raise CliError(str(error.get("code", "DEVICE_ERROR")),
                       str(error.get("message", "Operation failed")), result.get("operation_id"))
    if exit_code != 0 or not isinstance(result.get("data"), dict):
        raise CliError("OUTCOME_UNKNOWN" if writing else "INVALID_RESPONSE", "CLI exit status or data is invalid.")
    data = result["data"]
    if writing and data.get("completion") != expected_completion:
        raise CliError("OUTCOME_UNKNOWN", "Device modification has not been verified.", result.get("operation_id"))
    return data


class Client:
    def __init__(self, exe: Path, cache: Path, version: str):
        self.exe, self.cache, self.version = Path(exe), Path(cache), version

    def call(self, args: list[str], *, writing=False, timeout=300, online=False, expected_completion="verified") -> dict:
        if not self.exe.is_file():
            raise CliError("RUNTIME_MISSING", "Run scripts/setup.ps1 or reinstall this product.")
        if "--device" in args and args[:2] != ["firmware", "catalog"]:
            self._check_target(args[args.index("--device") + 1])
        command = [str(self.exe), *map(str, args), "--json", "--cache-dir", str(self.cache),
                   "--timeout", str(timeout), "--wait", "90"]
        command.append("--verified-https" if online else "--offline")
        # communicate waits for CDM's own bounded deadline. Never kill a write from the UI.
        try:
            completed = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as exc:
            raise CliError("RUNTIME_ERROR", str(exc)) from exc
        result = parse_result(completed.stdout, completed.returncode, writing, expected_completion)
        if writing:
            self.last_operation_id = json.loads(completed.stdout).get("operation_id")
        return result

    def handshake(self):
        data = self.call(["version"], timeout=30)
        if data.get("version") != self.version or data.get("cli_schema_version") != 1:
            raise CliError("VERSION_MISMATCH", "The installed CDM runtime does not match cdm-runtime.lock.json.")
        return data

    def devices(self):
        return self.call(["devices", "list"])["devices"]

    def _check_target(self, identifier):
        rows = [row for row in self.devices() if row.get("id") == identifier]
        if not rows:
            raise CliError("TARGET_NOT_FOUND", "The selected device is no longer present.")
        if len(rows) != 1:
            raise CliError("TARGET_AMBIGUOUS", "The selected device ID is not unique.")
        target = rows[0]
        if not str(target.get("backend", "")).casefold().startswith("xlapi"):
            return
        try:
            nodes = present_vector_nodes()
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            raise CliError("VECTOR_TARGET_UNVERIFIED", "Cannot enumerate present Vector USB devices.") from exc
        if not matches_vector_port(target, nodes):
            raise CliError("VECTOR_TARGET_UNVERIFIED", "Cannot bind the selected Vector target to one USB port.")

    def info(self, device):
        return self.call(["device", "info", "--device", device])

    def catalog(self, device=None, channel="stable"):
        args = ["firmware", "catalog", "--channel", channel]
        if device:
            args.extend(["--device", device])
        return self.call(args)["firmware"]

    def import_zip(self, path, channel="stable"):
        return self.call(["releases", "import", "--file", str(path), "--channel", channel])

    def check_online(self, channel):
        return self.call(["releases", "check", "--channel", channel], online=True)

    def download(self, channel, version):
        return self.call(["releases", "download", "--channel", channel, "--version", version], online=True)

    def operation(self, identifier):
        if not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise CliError("INVALID_ARGUMENT", "Invalid operation ID")
        record = self.call(["operations", "show", "--id", identifier])
        if record.get("schema_version") != 1 or record.get("operation_id") != identifier:
            raise CliError("INVALID_RESPONSE", "Unexpected operation record")
        return ((record.get("data") or {}).get("completion")
                or (record.get("error") or {}).get("code") or "OUTCOME_UNKNOWN")

    def set_mode(self, device, uid, mode):
        data = self.call(["modes", "set", "--device", device, "--expect-uid", uid,
                          "--mode", mode, "--yes"], writing=True, expected_completion="acknowledged")
        if data.get("uid") != uid or data.get("mode") != mode:
            raise CliError("OUTCOME_UNKNOWN", "Unmatched mode acknowledgement")
        return data

    def uninstall(self, device, uid, firmware, *, preview):
        args = ["firmware", "uninstall", "--device", device, "--expect-uid", uid,
                "--firmware", firmware, "--dry-run" if preview else "--yes"]
        result = self.call(args, writing=not preview)
        if preview and (result.get("completion") != "preview" or result.get("device") != device
                or result.get("action") != "uninstall" or result.get("uid") != uid
                or (result.get("firmware") or {}).get("id") != firmware):
            raise CliError("INVALID_RESPONSE", "Unexpected uninstall preview")
        return result

    def termination(self, device, channel, uid=None, enabled=None):
        args = ["termination", "get" if enabled is None else "set", "--device", device, "--channel", str(channel)]
        if enabled is not None:
            args += ["--expect-uid", uid, "--state", "on" if enabled else "off", "--yes"]
        return self.call(args, writing=enabled is not None)

    def switch(self, device, uid, firmware):
        return self.call(["firmware", "switch", "--device", device, "--expect-uid", uid,
                          "--firmware", firmware, "--yes"], writing=True)

    def install(self, device, uid, firmware, version, plan_id=None, *, replace=None, target_slot=None, channel="stable"):
        args = ["firmware", "install", "--device", device, "--expect-uid", uid,
                "--firmware", firmware, "--version", version, "--channel", channel]
        if replace and target_slot:
            raise ValueError("Select a single installation target")
        if replace:
            args += ["--replace", replace]
        if target_slot:
            args += ["--target-slot", target_slot]
        args += ["--plan-id", plan_id, "--yes"] if plan_id else ["--dry-run"]
        result = self.call(args, writing=plan_id is not None)
        if plan_id is None:
            plan = result.get("plan")
            if (not isinstance(plan, dict) or result.get("completion") != "preview"
                    or any(plan.get(k) != v for k, v in {
                        "device": device, "uid": uid, "firmware": firmware, "version": version,
                        "preserve_other_firmware": True, "replace": replace, "target_slot": target_slot}.items())
                    or not re.fullmatch(r"[0-9a-f]{64}", str(plan.get("plan_id", "")))
                    or type(plan.get("size_bytes")) is not int or plan["size_bytes"] <= 0
                    or not plan.get("name") or not plan.get("firmware_version")):
                raise CliError("INVALID_RESPONSE", "Installation preview does not match the requested device and firmware.")
        return result


def device_view(data):
    """Map only documented display fields, tolerating absent optional data."""
    license_info = data.get("overview", {}).get("license", {}) or {}
    try:
        channels = max(0, min(64, int(license_info.get("max_channels_can") or license_info.get("max_channels") or 0)))
    except (ValueError, TypeError):
        channels = 0
    firmware = [{k: row.get(k) for k in ("id", "name", "version", "running", "size_kib")}
                for row in data.get("firmware", [])]
    return {"uid": data.get("uid"), "channels": channels, "firmware": firmware}


def plan_view(plan):
    return {key: plan.get(key) for key in ("plan_id", "device", "uid", "firmware", "name", "version",
                                         "firmware_version", "size_bytes", "preserve_other_firmware", "replace")}
