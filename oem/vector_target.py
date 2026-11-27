"""Read-only Windows PnP check for Vector XL target selection."""

import ctypes
import re
from ctypes import byref, wintypes


# cfgmgr32.h, Windows Configuration Manager
CM_GETIDLIST_FILTER_ENUMERATOR = 0x00000001
CM_GETIDLIST_FILTER_PRESENT = 0x00000100
CM_DRP_SERVICE = 0x05
CM_DRP_CLASS = 0x08
CM_DRP_LOCATION_PATHS = 0x24
CR_BUFFER_SMALL = 0x1A
CR_NO_SUCH_VALUE = 0x25


def _check(status):
    if status != 0:
        raise OSError(f"Windows Configuration Manager returned 0x{status:02X}")


def _usb_instance_ids(cm):
    flags = CM_GETIDLIST_FILTER_ENUMERATOR | CM_GETIDLIST_FILTER_PRESENT
    length = wintypes.ULONG()
    # A hot-plug can grow the MULTI_SZ between sizing and reading the list.
    for _ in range(3):
        _check(cm.CM_Get_Device_ID_List_SizeW(byref(length), "USB", flags))
        buffer = ctypes.create_unicode_buffer(length.value)
        status = cm.CM_Get_Device_ID_ListW("USB", buffer, length, flags)
        if status != CR_BUFFER_SMALL:
            _check(status)
            return buffer[:].rstrip("\0").split("\0")
    raise OSError("USB device list kept changing")


def _property(cm, devinst, key):
    length = wintypes.ULONG()
    kind = wintypes.ULONG()
    status = cm.CM_Get_DevNode_Registry_PropertyW(devinst, key, byref(kind), None, byref(length), 0)
    if status == CR_NO_SUCH_VALUE and key != CM_DRP_LOCATION_PATHS:
        return []
    if status != CR_BUFFER_SMALL:
        _check(status)
    buffer = ctypes.create_string_buffer(length.value)
    _check(cm.CM_Get_DevNode_Registry_PropertyW(devinst, key, byref(kind), buffer, byref(length), 0))
    expected_type = 7 if key == CM_DRP_LOCATION_PATHS else 1  # REG_MULTI_SZ / REG_SZ
    if kind.value != expected_type:
        raise ValueError(f"Unexpected registry type for device property {key}")
    return buffer.raw[:length.value].decode("utf-16-le").rstrip("\0").split("\0")


def present_vector_nodes():
    cm = ctypes.windll.cfgmgr32
    nodes = []
    for instance in _usb_instance_ids(cm):
        # The separator after the PID excludes composite MI_ interface nodes.
        match = re.match(r"^USB\\VID_1248&PID_([0-9A-F]{4})\\", instance, re.I)
        if not match:
            continue
        devinst = wintypes.ULONG()
        _check(cm.CM_Locate_DevNodeW(byref(devinst), instance, 0))
        if match[1].upper() not in {"1050", "1071"}:
            device_class = _property(cm, devinst, CM_DRP_CLASS)
            service = _property(cm, devinst, CM_DRP_SERVICE)
            if not (any(value.casefold() == "vector-hardware" for value in device_class)
                    or any(re.match(r"^vn[0-9]", value, re.I) for value in service)):
                continue
        nodes.append({"id": instance, "paths": _property(cm, devinst, CM_DRP_LOCATION_PATHS)})
    return nodes


def matches_vector_port(device, nodes):
    if not isinstance(nodes, list) or len(nodes) != 1 or not isinstance(nodes[0], dict):
        return False
    node = nodes[0]
    selected = device.get("usb_node") or device.get("instance_id")
    if not isinstance(selected, str) or selected.upper() != str(node.get("id")).upper():
        return False
    # LocationPaths can include alternate ACPI paths. Compare complete USB port
    # paths, including PCI controller and hub chain, across the two enumerations.
    routes = str(device.get("location") or "").upper().split(";")
    paths = node.get("paths")
    return isinstance(paths, list) and any(
        isinstance(path, str) and re.search(r"#USBROOT\(\d+\)(?:#USB\(\d+\))+$", path.upper())
        and path.upper() in [route.strip() for route in routes] for path in paths
    )
