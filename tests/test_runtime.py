import hashlib
import json
import zipfile
import pytest
from prepare_runtime import acquire, safe_extract, prepare


def make_zip(tmp_path,filename='package/file.txt'):
    path=tmp_path/'archive.zip'
    with zipfile.ZipFile(path,'w') as archive:archive.writestr(filename,'example')
    lock={'version':'0.8.6','tag':'CDM-0.8.6','cli_schema':1,'size':path.stat().st_size,
          'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'urls':[]}
    return path,lock


def test_local_archive_and_wrong_hash(tmp_path):
    path,lock=make_zip(tmp_path)
    assert acquire(lock,path,tmp_path)==path
    lock['sha256']='0'*64
    with pytest.raises(ValueError,match='SHA-256'):acquire(lock,path,tmp_path)


@pytest.mark.parametrize('name',['../outside','/absolute','C:/outside','folder/../../outside','file:stream'])
def test_reject_zip_paths(tmp_path,name):
    path,_=make_zip(tmp_path,name)
    with pytest.raises(ValueError,match='Unsafe'):safe_extract(path,tmp_path/'out')
    assert not (tmp_path/'outside').exists()


def test_source_archive_without_git_repeat_setup(tmp_path,monkeypatch):
    path,lock=make_zip(tmp_path,'package/CANmeleon-device-manager.exe')
    (tmp_path/'cdm-runtime.lock.json').write_text(json.dumps(lock))
    monkeypatch.setattr('prepare_runtime.check_runtime',lambda *a:None)
    prepare(path,tmp_path);prepare(path,tmp_path)
    assert (tmp_path/'.runtime/cdm/CANmeleon-device-manager.exe').read_text()=='example'
    assert not (tmp_path/'.runtime/previous').exists()


def test_download_fallback_and_partial_cleanup(tmp_path,monkeypatch):
    import io
    path,lock=make_zip(tmp_path);content=path.read_bytes()
    lock['urls']=['https://one.example/download/CDM-0.8.6/runtime.zip','https://two.example/download/CDM-0.8.6/runtime.zip']
    calls=[]
    def open_url(url,**kwargs):
        calls.append(url)
        if len(calls)==1:raise OSError('unavailable')
        return io.BytesIO(content)
    monkeypatch.setattr('prepare_runtime.urllib.request.urlopen',open_url)
    result=acquire(lock,root=tmp_path)
    assert result.read_bytes()==content and len(calls)==2
    acquire(lock,root=tmp_path)
    assert len(calls)==2 and not list((tmp_path/'.cache').glob('*.partial'))

def test_local_candidate_stages_beside_its_lock(tmp_path, monkeypatch):
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    archive, lock = make_zip(candidate, 'package/CANmeleon-device-manager.exe')
    lock_path = candidate / 'candidate.lock.json'
    lock_path.write_text(json.dumps(lock))
    monkeypatch.setattr('prepare_runtime.check_runtime', lambda *args: None)

    prepare(archive, tmp_path, lock_path=lock_path)

    assert (candidate / '.runtime/cdm/CANmeleon-device-manager.exe').is_file()
    assert not (tmp_path / '.runtime').exists()
    with pytest.raises(ValueError, match='requires its runtime archive'):
        prepare(root=tmp_path, lock_path=lock_path)
