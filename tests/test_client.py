import json
from types import SimpleNamespace
import pytest
from oem.client import Client, CliError, parse_result, device_view, plan_view


def envelope(data, **kwargs):
    return json.dumps(dict(schema_version=1, ok=True, data=data, **kwargs))


def test_verified_write_only():
    assert parse_result(envelope({'completion':'verified'}),0,True)['completion']=='verified'
    for result in ('not json', envelope({'completion':'acknowledged'}), envelope({})):
        with pytest.raises(CliError) as error: parse_result(result,0,True)
        assert error.value.code=='OUTCOME_UNKNOWN'


@pytest.mark.parametrize('code', ['TARGET_NOT_FOUND','TARGET_MISMATCH','STALE_PLAN','DEVICE_BUSY','TIMEOUT','OUTCOME_UNKNOWN','INVALID_PACKAGE'])
def test_errors_remain_machine_readable(code):
    payload=json.dumps({'schema_version':1,'ok':False,'error':{'code':code,'message':'detail'},'operation_id':'job'})
    with pytest.raises(CliError) as error:parse_result(payload,8)
    assert (error.value.code,error.value.operation_id)==(code,'job')


@pytest.mark.parametrize('payload,exit_code', [('garbage',0),('[]',0),('{"schema_version":2,"ok":true}',0),(envelope({}),1),(envelope([]),0)])
def test_reject_invalid_responses(payload,exit_code):
    with pytest.raises(CliError):parse_result(payload,exit_code)


def test_public_views_omit_layout():
    data={'uid':'abc','overview':{'license':{'max_channels_can':4},'layout':'private'},'firmware':[{'id':'f','address':12,'record':{'private':True},'name':'GS USB'}]}
    view=device_view(data)
    assert view['channels']==4 and 'overview' not in view and 'record' not in view['firmware'][0]
    assert 'address' not in plan_view({'plan_id':'p','address':12,'layout':[]})
    assert device_view({'overview':{'license':{'max_channels':'bad'}}})['channels']==0


def test_execution_is_bound_and_uses_argument_array(tmp_path,monkeypatch):
    exe=tmp_path/'space path.exe';exe.touch();calls=[]
    def run(command,**options):
        calls.append((command,options))
        return SimpleNamespace(stdout=envelope({'completion':'verified'}),returncode=0)
    monkeypatch.setattr('oem.client.subprocess.run',run)
    client=Client(exe,tmp_path/'cache','0.8.6')
    monkeypatch.setattr(client, 'devices', lambda: [{'id': 'dev', 'backend': 'pcan'}])
    client.install('dev','UID','fw','8.15.2','plan')
    args,options=calls[0]
    for token in ['--expect-uid','UID','--plan-id','plan','--yes','--offline']:assert token in args
    assert args[0]==str(exe) and options['stdin']==-3 and options['stdout']==-1
    assert 'shell' not in options and 'timeout' not in options


def test_handshake_rejects_wrong_version(monkeypatch,tmp_path):
    client=Client(tmp_path/'exe',tmp_path,'0.8.6')
    monkeypatch.setattr(client,'call',lambda *a,**k:{'version':'0.8.5','cli_schema_version':1})
    with pytest.raises(CliError,match='does not match'):client.handshake()


def test_networking_is_explicit_and_pins_download_version(tmp_path, monkeypatch):
    exe = tmp_path / "cdm.exe"
    exe.touch()
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(stdout=envelope({}), returncode=0)
    monkeypatch.setattr("oem.client.subprocess.run", run)
    client = Client(exe, tmp_path, "0.8.6")
    monkeypatch.setattr(client, "devices", lambda: [{"id": "d", "backend": "pcan"}])
    client.info("d")
    client.check_online("beta")
    client.download("stable", "8.15.2")
    assert "--offline" in commands[0] and "--verified-https" not in commands[0]
    assert all("--verified-https" in cmd and "--offline" not in cmd for cmd in commands[1:])
    assert commands[2][1:7] == ["releases", "download", "--channel", "stable", "--version", "8.15.2"]


def test_uninstall_and_mode_responses_are_bound_to_selection(tmp_path, monkeypatch):
    client = Client(tmp_path / "cdm.exe", tmp_path, "0.8.6")
    monkeypatch.setattr(client, "call", lambda *a, **k: {"completion": "preview", "action": "uninstall",
                        "uid": "uid", "device": "d", "firmware": {"id": "other"}})
    with pytest.raises(CliError, match="uninstall preview"):
        client.uninstall("d", "uid", "expected", preview=True)
    monkeypatch.setattr(client, "call", lambda *a, **k: {"completion": "acknowledged", "mode": "wrong", "uid": "uid"})
    with pytest.raises(CliError) as error:
        client.set_mode("d", "uid", "requested")
    assert error.value.code == "OUTCOME_UNKNOWN"


def test_operation_lookup_checks_identity_and_hides_internal_details(tmp_path, monkeypatch):
    client = Client(tmp_path / "cdm.exe", tmp_path, "0.8.6")
    identifier = "1"*32
    record = dict(schema_version=1, operation_id=identifier, ok=True, data={"completion": "verified", "layout": []})
    monkeypatch.setattr(client, "call", lambda *a, **k: record)
    assert client.operation(identifier) == "verified"
    with pytest.raises(CliError):
        client.operation("2"*32)
    with pytest.raises(CliError):
        client.operation("../invalid")


@pytest.mark.parametrize('payload', [
    {'schema_version': True, 'ok': True, 'data': {}},
    {'schema_version': 1, 'ok': False, 'error': 'bad'},
    {'schema_version': 1, 'ok': False},
])
def test_malformed_write_error_is_unknown(payload):
    with pytest.raises(CliError) as error: parse_result(json.dumps(payload),1,True)
    assert error.value.code=='OUTCOME_UNKNOWN'


@pytest.mark.parametrize('changed', [{'uid':'other'}, {'plan_id':'bad'}, {'replace':'old'}, {'version':'other'}, {'size_bytes':0}])
def test_preview_must_match_selection(changed,tmp_path,monkeypatch):
    client=Client(tmp_path/'exe',tmp_path,'0.8.6')
    plan=dict(device='dev',uid='UID',firmware='gs-usb',version='8.15.2',plan_id='a'*64,
              preserve_other_firmware=True,replace=None,size_bytes=1024,name='GS USB',firmware_version='8.15.2')
    plan.update(changed)
    monkeypatch.setattr(client,'call',lambda *a,**k:dict(completion='preview',plan=plan))
    with pytest.raises(CliError):client.install('dev','UID','gs-usb','8.15.2')

VECTOR_PORT = "PCIROOT(0)#PCI(0801)#PCI(0004)#USBROOT(0)#USB(2)"
VECTOR_ID = r"USB\VID_1248&PID_1071\SERIAL"
VECTOR_DEVICE = dict(id="selected", backend="xlapi/python-can", usb_node=VECTOR_ID,
                     location=f"{VECTOR_PORT}; ACPI(TEST)")
VECTOR_NODE = dict(id=VECTOR_ID, paths=["ACPI(TEST)", VECTOR_PORT])


@pytest.mark.parametrize("nodes", [
    [], [VECTOR_NODE, dict(id="second", paths=[])],
    [dict(id=VECTOR_ID, paths=[VECTOR_PORT.replace("PCI(0004)", "PCI(0003)")])],
    [dict(id="different", paths=[VECTOR_PORT])], [dict(id=VECTOR_ID, paths=[])],
])
def test_vector_target_requires_one_matching_physical_port(tmp_path, monkeypatch, nodes):
    exe = tmp_path / "cdm.exe"
    exe.touch()
    client = Client(exe, tmp_path, "0.9.0")
    monkeypatch.setattr(client, "devices", lambda: [VECTOR_DEVICE])
    monkeypatch.setattr("oem.client.present_vector_nodes", lambda: nodes)
    monkeypatch.setattr("oem.client.subprocess.run", lambda *a, **kw: pytest.fail("command sent"))
    with pytest.raises(CliError) as error:
        client.info("selected")
    assert error.value.code == "VECTOR_TARGET_UNVERIFIED"


def test_vector_install_rechecks_after_preview(tmp_path, monkeypatch):
    exe = tmp_path / "cdm.exe"
    exe.touch()
    client = Client(exe, tmp_path, "0.9.0")
    monkeypatch.setattr(client, "devices", lambda: [VECTOR_DEVICE])
    snapshots = iter([[VECTOR_NODE], [VECTOR_NODE, dict(id="second", paths=[])]])
    monkeypatch.setattr("oem.client.present_vector_nodes", lambda: next(snapshots))
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        plan = dict(device="selected", uid="uid", firmware="fw", version="v", plan_id="a"*64,
                    size_bytes=1024, preserve_other_firmware=True, firmware_version="v", name="Firmware")
        return SimpleNamespace(stdout=envelope(dict(completion="preview", plan=plan)), returncode=0)
    monkeypatch.setattr("oem.client.subprocess.run", run)
    plan = client.install("selected", "uid", "fw", "v")["plan"]
    with pytest.raises(CliError) as error:
        client.install("selected", "uid", "fw", "v", plan["plan_id"])
    assert error.value.code == "VECTOR_TARGET_UNVERIFIED"
    assert len(calls) == 1 and "--dry-run" in calls[0]


def test_vector_inventory_failure_blocks_write(tmp_path, monkeypatch):
    exe = tmp_path / "cdm.exe"
    exe.touch()
    client = Client(exe, tmp_path, "0.9.0")
    monkeypatch.setattr(client, "devices", lambda: [VECTOR_DEVICE])
    def denied():
        raise PermissionError("denied")
    monkeypatch.setattr("oem.client.present_vector_nodes", denied)
    with pytest.raises(CliError) as error:
        client.set_mode("selected", "uid", "mode")
    assert error.value.code == "VECTOR_TARGET_UNVERIFIED"
