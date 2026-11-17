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
    client.install('dev','UID','fw','8.15.2','plan')
    args,options=calls[0]
    for token in ['--expect-uid','UID','--plan-id','plan','--yes','--offline']:assert token in args
    assert args[0]==str(exe) and options['stdin']==-3 and options['stdout']==-1
    assert 'shell' not in options and 'timeout' not in options


def test_handshake_rejects_wrong_version(monkeypatch,tmp_path):
    client=Client(tmp_path/'exe',tmp_path,'0.8.6')
    monkeypatch.setattr(client,'call',lambda *a,**k:{'version':'0.8.5','cli_schema_version':1})
    with pytest.raises(CliError,match='does not match'):client.handshake()


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
