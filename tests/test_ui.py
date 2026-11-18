import time
from pathlib import Path
import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication
from oem.client import CliError
from oem.config import load_brand
from oem.ui import Window, ERROR_HELP


class DemoClient:
    version='0.8.6'
    def termination(self, device, channel):
        return {'channel': channel, 'enabled': False}
    def handshake(self):return {'version':self.version}
    def devices(self):return [{'id':'device-a','name':'Demo X2','location':'USB(3)'}]
    def info(self,device):return {'uid':'1'*32,'overview':{'license':{'max_channels_can':2}},'firmware':[{'id':'f1','name':'KCAN X4','version':'8.15.2','running':True}]}
    def catalog(self,device):return [{'id':'gs-usb','name':'GS USB','version':'8.15.2','availability':'Available','reason':''}]


@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])


def wait(app,predicate):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        app.processEvents()
        if predicate():return
        time.sleep(.01)
    raise AssertionError('UI timed out')


@pytest.fixture
def window(app,tmp_path):
    root=Path(__file__).resolve().parent.parent
    win=Window(DemoClient(),load_brand(root),root,tmp_path/'settings.json')
    wait(app,lambda:win.ready and win.job is None)
    yield win
    wait(app,lambda:win.job is None)
    win.close()


def test_single_candidate_requires_connect_then_opens_firmware(window,app):
    assert window.device_table.currentRow()==0 and window.uid is None
    window.read_device()
    wait(app,lambda:window.job is None)
    assert window.uid=='1'*32 and len(window.checks)==2
    assert window.table.rowCount()==1
    window.language.setCurrentIndex(1)
    assert window.tabs.tabText(window.tabs.currentIndex())=='Firmware'
    assert window.table.horizontalHeaderItem(0).text()=='Firmware'


def test_unknown_result_disables_writes_until_read(window,app):
    window.read_device();wait(app,lambda:window.job is None)
    window.failed(CliError('OUTCOME_UNKNOWN','test'),True);window.update_actions()
    assert window.uncertain
    assert all(not b.isEnabled() for b,need in window.actions if need in ('write_channel','catalog','firmware'))
    window.read_device();wait(app,lambda:window.job is None)
    assert not window.uncertain


def test_busy_operation_blocks_close_and_duplicate(window,app):
    calls=[]
    window.start(lambda:(time.sleep(.1),calls.append(1)),lambda _:None,writing=True)
    window.start(lambda:calls.append(2),lambda _:None)
    event=QCloseEvent();window.closeEvent(event)
    assert not event.isAccepted()
    wait(app,lambda:window.job is None)
    assert calls==[1]


def test_failed_refresh_cannot_reuse_previous_identity(window,app,monkeypatch):
    window.read_device();wait(app,lambda:window.job is None)
    def disconnected(*args): raise CliError('TARGET_NOT_FOUND','disconnected')
    monkeypatch.setattr(window.client,'info',disconnected)
    window.read_device();wait(app,lambda:window.job is None)
    assert window.uid is None and window.table.rowCount()==0
    assert all(not b.isEnabled() for b,need in window.actions if need in ('write_channel','catalog','firmware'))


@pytest.mark.parametrize('confirm',[False,True])
def test_install_requires_preview_then_confirmation(window,app,monkeypatch,confirm):
    window.read_device();wait(app,lambda:window.job is None)
    calls=[]
    def install(device,uid,firmware,version,plan_id=None):
        calls.append((device,uid,firmware,version,plan_id))
        if plan_id: return {'completion':'verified'}
        return {'completion':'preview','plan':{'plan_id':'a'*64,'name':'GS USB','firmware_version':'8.15.2','size_bytes':1024}}
    monkeypatch.setattr(window.client,'install',install,raising=False)
    monkeypatch.setattr(window,'confirm',lambda _:confirm)
    window.preview_install();wait(app,lambda:window.job is None)
    assert len(calls)==(2 if confirm else 1)
    assert calls[0]==('device-a','1'*32,'gs-usb','8.15.2',None)
    if confirm: assert calls[1][-1]=='a'*64


def test_write_timeout_never_retries(window,app,monkeypatch):
    window.read_device();wait(app,lambda:window.job is None)
    calls=[]
    def termination(*args):
        calls.append(args)
        raise CliError('TIMEOUT','simulated write interruption')
    monkeypatch.setattr(window.client,'termination',termination,raising=False)
    monkeypatch.setattr(window,'confirm',lambda _:True)
    window.checks[1].setChecked(True);window.set_termination();wait(app,lambda:window.job is None)
    assert len(calls)==1 and window.uncertain
    assert all(not b.isEnabled() for b,need in window.actions if need=='write_channel')


@pytest.mark.parametrize('code',list(ERROR_HELP))
def test_error_guidance_is_bilingual(window,code):
    for language in (0,1):
        window.language.setCurrentIndex(language)
        window.failed(CliError(code,'technical detail'))
        assert ERROR_HELP[code][language] in window.status.text()
        assert 'technical detail' not in window.status.text()

def test_disconnect_clears_device_and_multidevice_requires_selection(window, app, monkeypatch):
    window.read_device()
    wait(app, lambda: window.job is None)
    monkeypatch.setattr(window.client, 'devices', lambda: [{'id': 'a'}, {'id': 'b'}])
    window.refresh_devices()
    wait(app, lambda: window.job is None)
    assert window.flow.currentIndex() == 0 and window.uid is None
    assert window.device_table.currentRow() == -1
    assert window.catalog.count() == 1 and window.install_button.isHidden()


def test_partial_channel_apply_stops_until_fresh_read(window, app, monkeypatch):
    window.read_device()
    wait(app, lambda: window.job is None)
    writes = []
    def write(device, channel, uid=None, enabled=None):
        if uid is None:
            return {"channel": channel, "enabled": True}
        writes.append((channel, uid, enabled))
        if channel == 2:
            raise CliError('TIMEOUT', 'unknown result')
    monkeypatch.setattr(window.client, 'termination', write)
    monkeypatch.setattr(window, 'confirm', lambda _: True)
    for box in window.checks.values():
        box.setChecked(True)
    window.set_termination()
    wait(app, lambda: window.job is None)
    assert writes == [(1, '1'*32, True), (2, '1'*32, True)]
    assert window.uncertain
    window.set_termination()
    assert len(writes) == 2
