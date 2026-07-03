from dataclasses import fields

from zzz_od.backend.schemas import RunStatusResult


def test_run_status_result_fields():
    names = {f.name for f in fields(RunStatusResult)}
    assert names == {
        'state', 'source', 'app', 'started_at', 'duration_seconds',
        'current_node', 'retry_count', 'last_status', 'failed_node',
    }


def test_run_status_result_defaults():
    r = RunStatusResult(state='idle')
    assert r.source is None and r.app is None
    assert r.current_node is None and r.last_status is None and r.failed_node is None
