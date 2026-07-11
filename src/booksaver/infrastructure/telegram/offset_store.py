from __future__ import annotations

from booksaver.domain.value_objects import DataDirectory

_OFFSET_FILENAME = "telegram_offset"


class TelegramOffsetStore:
    """Persists the last-processed Telegram update offset (US-023).

    A restart neither drops nor replays updates: the offset is written after
    each processed batch, mirroring `LocalSessionRepository`'s plain-file pattern.
    """

    def __init__(self, data_dir: DataDirectory) -> None:
        self._path = data_dir.path / _OFFSET_FILENAME

    def load(self) -> int | None:
        try:
            return int(self._path.read_text().strip())
        except (OSError, ValueError):
            return None

    def save(self, offset: int) -> None:
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._path.write_text(str(offset))
        self._path.chmod(0o600)
