from __future__ import annotations

from pathlib import Path

from booksaver.domain.value_objects import DataDirectory
from booksaver.infrastructure.telegram.offset_store import TelegramOffsetStore


def _data_dir(tmp_path: Path) -> DataDirectory:
    d = tmp_path / "booksaver"
    d.mkdir()
    return DataDirectory(path=d)


def test_load_returns_none_when_no_file_exists(tmp_path: Path) -> None:
    store = TelegramOffsetStore(_data_dir(tmp_path))
    assert store.load() is None


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    store = TelegramOffsetStore(_data_dir(tmp_path))
    store.save(42)
    assert store.load() == 42


def test_save_overwrites_previous_offset(tmp_path: Path) -> None:
    store = TelegramOffsetStore(_data_dir(tmp_path))
    store.save(1)
    store.save(2)
    assert store.load() == 2


def test_load_returns_none_for_corrupt_file(tmp_path: Path) -> None:
    data_dir = _data_dir(tmp_path)
    (data_dir.path / "telegram_offset").write_text("not-a-number")
    store = TelegramOffsetStore(data_dir)
    assert store.load() is None


def test_save_persists_across_new_store_instance(tmp_path: Path) -> None:
    data_dir = _data_dir(tmp_path)
    TelegramOffsetStore(data_dir).save(7)
    # Simulate a restart: a brand-new store instance reads the same file.
    assert TelegramOffsetStore(data_dir).load() == 7


def test_saved_file_is_owner_only_permissions(tmp_path: Path) -> None:
    data_dir = _data_dir(tmp_path)
    store = TelegramOffsetStore(data_dir)
    store.save(1)
    mode = (data_dir.path / "telegram_offset").stat().st_mode
    assert oct(mode)[-3:] == "600"
