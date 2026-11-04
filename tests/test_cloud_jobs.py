from types import SimpleNamespace
import sys
import pytest
from factory_lab import cloud

class Store(dict):
    def put(self,key,value,skip_if_exists=False):
        if skip_if_exists and key in self:return False
        self[key]=value
        return True


def test_cloud_admission_rejects_simultaneous_jobs(monkeypatch):
    jobs=Store(); calls=[]
    monkeypatch.setattr(cloud,'store',lambda:jobs)
    monkeypatch.setitem(sys.modules,'modal',SimpleNamespace(Function=SimpleNamespace(from_name=lambda *a:SimpleNamespace(spawn=lambda *a:calls.append(a)))))
    job=cloud.start('episode',{'scenario':{},'policy':'meta'})
    assert jobs[job]['status']=='running' and len(calls)==1
    with pytest.raises(ValueError,match='already running'):
        cloud.start('episode',{'scenario':{},'policy':'meta'})
    assert len(calls)==1


def test_failed_dispatch_releases_admission(monkeypatch):
    jobs=Store()
    monkeypatch.setattr(cloud,'store',lambda:jobs)
    def fail(*a):raise RuntimeError('dispatch unavailable')
    monkeypatch.setitem(sys.modules,'modal',SimpleNamespace(Function=SimpleNamespace(from_name=fail)))
    with pytest.raises(RuntimeError,match='dispatch unavailable'):
        cloud.start('episode',{'scenario':{},'policy':'meta'})
    assert 'active' not in jobs
