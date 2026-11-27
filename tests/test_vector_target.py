from types import SimpleNamespace

import pytest

from oem import vector_target as target


def test_enumeration_includes_vector_roots_and_excludes_interfaces(monkeypatch):
    ids = [
        r"USB\VID_1248&PID_1071\KNOWN",
        r"USB\VID_1248&PID_1071&MI_00\INTERFACE",
        r"USB\VID_1248&PID_1200\BY_CLASS",
        r"USB\VID_1248&PID_1400\BY_SERVICE",
        r"USB\VID_1248&PID_1500\OTHER",
    ]

    def locate(instance_out, instance, _flags):
        instance_out._obj.value = ids.index(instance)
        return 0

    def prop(_cm, instance, key):
        if key == target.CM_DRP_LOCATION_PATHS:
            return ["PORT-" + str(instance.value)]
        if key == target.CM_DRP_CLASS and instance.value == 2:
            return ["Vector-Hardware"]
        if key == target.CM_DRP_SERVICE and instance.value == 3:
            return ["VN1630"]
        return []

    cm = SimpleNamespace(CM_Locate_DevNodeW=locate)
    monkeypatch.setattr(target.ctypes, "windll", SimpleNamespace(cfgmgr32=cm), raising=False)
    monkeypatch.setattr(target, "_usb_instance_ids", lambda cm: ids)
    monkeypatch.setattr(target, "_property", prop)
    assert target.present_vector_nodes() == [
        {"id": ids[i], "paths": ["PORT-" + str(i)]} for i in (0, 2, 3)
    ]


def test_disappearing_vector_device_fails_closed(monkeypatch):
    cm = SimpleNamespace(CM_Locate_DevNodeW=lambda *_: 0x0D)
    monkeypatch.setattr(target.ctypes, "windll", SimpleNamespace(cfgmgr32=cm), raising=False)
    monkeypatch.setattr(target, "_usb_instance_ids", lambda cm: [r"USB\VID_1248&PID_1050\GONE"])
    with pytest.raises(OSError):
        target.present_vector_nodes()
