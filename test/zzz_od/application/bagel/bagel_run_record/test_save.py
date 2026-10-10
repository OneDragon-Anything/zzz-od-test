from pathlib import Path

import pytest
import yaml

from zzz_od.application.bagel.bagel_run_record import BagelRunRecord


def test_failed_replace_preserves_disk(
    record: BagelRunRecord, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """当前运行状态保存失败时保留旧文件，并清理临时文件。"""
    before = Path(record.file_path).read_bytes()

    def fail_replace(self: Path, target: Path) -> None:
        """模拟 Windows 文件占用等写入错误。"""
        raise PermissionError('模拟文件占用')

    monkeypatch.setattr(Path, 'replace', fail_replace)
    with pytest.raises(PermissionError):
        record.update_status(BagelRunRecord.STATUS_RUNNING)
    assert Path(record.file_path).read_bytes() == before
    assert BagelRunRecord(99).get('collection') == record.get('collection')
    assert not list(Path(record.file_path).parent.glob('*.tmp'))


@pytest.mark.parametrize(
    'content',
    [
        'collection: [',
    ],
)
def test_corrupt_file_is_rejected(record: BagelRunRecord, content: str) -> None:
    """损坏记录不能吞异常后按空文件继续运行。"""
    Path(record.file_path).write_text(content, encoding='utf-8')
    with pytest.raises((ValueError, yaml.YAMLError)):
        BagelRunRecord(99)


@pytest.mark.parametrize(
    'phase',
    [
        'finished',
    ],
)
def test_status_updates_preserve_legacy_collection(
    record: BagelRunRecord, legacy_collection: dict, phase: str,
) -> None:
    """旧局处于任意阶段时，当前任务更新或重置状态都不能推进旧记账。"""
    inventory = [{'name': '测试武备', 'variant': 'III', 'quantity': 1}]
    legacy_collection['pending']['secured'] = inventory
    if phase == 'depositing':
        legacy_collection['pending'].update(phase=phase, warehouse_before=inventory)
    elif phase == 'finished':
        legacy_collection.update(
            pending=None, deposited=inventory,
            last_round={'id': 'legacy-round', 'deposited': inventory, 'outcome': '主动退出'},
        )
    path = Path(record.file_path)
    path.write_text(yaml.safe_dump({'collection': legacy_collection}, allow_unicode=True), encoding='utf-8')
    current = BagelRunRecord(99)
    for status in (current.STATUS_RUNNING, current.STATUS_SUCCESS, current.STATUS_FAIL):
        current.update_status(status)
        assert BagelRunRecord(99).get('collection') == legacy_collection
    current.reset_record()
    reloaded = BagelRunRecord(99)
    assert reloaded.run_status == current.STATUS_WAIT
    assert reloaded.get('collection') == legacy_collection


def test_new_record_only_saves_application_status() -> None:
    """新账号不再生成旧物资任务，正常保存应用状态。"""
    record = BagelRunRecord(98)
    record.update_status(record.STATUS_SUCCESS)
    reloaded = BagelRunRecord(98)
    assert reloaded.is_done
    assert 'collection' not in reloaded.data
