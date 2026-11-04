import sys
from types import SimpleNamespace

import pytest
from factory_lab.budget import BudgetLedger


def test_cloud_reservation_commits_before_return(tmp_path, monkeypatch):
    commits = []
    class Volume:
        def commit(self):
            assert 'reserved' in (tmp_path/'ledger').read_text()
            commits.append(True)
    monkeypatch.setenv('FACTORY_MODAL_VOLUME','test-volume')
    monkeypatch.setitem(sys.modules,'modal',SimpleNamespace(Volume=SimpleNamespace(from_name=lambda name:Volume())))
    ledger = BudgetLedger(tmp_path/'ledger')
    request = ledger.reserve('muse-spark-1.3',.1)
    assert request and commits == [True]


def test_cloud_persistence_failure_blocks_admission(tmp_path, monkeypatch):
    def fail():
        raise RuntimeError('persistence unavailable')
    monkeypatch.setenv('FACTORY_MODAL_VOLUME','test-volume')
    monkeypatch.setitem(sys.modules,'modal',SimpleNamespace(Volume=SimpleNamespace(from_name=lambda name:SimpleNamespace(commit=fail))))
    with pytest.raises(RuntimeError,match='persistence unavailable'):
        BudgetLedger(tmp_path/'ledger').reserve('muse-spark-1.3',.1)
