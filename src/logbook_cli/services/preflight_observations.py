"""Short-lived self-check results, independent of the durable send journal."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from logbook_cli import state
from logbook_cli.document import EXIT_REFUSED, LbError
from logbook_cli.storage import replace_bytes_at

MAX_CACHE_BYTES = 4 * 1024 * 1024
ObservationKey = tuple[str, str, str, str]


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("self-check time requires a timezone")
    return parsed


@dataclass(frozen=True)
class Observation:
    task_id: str
    check_id: str
    subject_id: str
    environment_ref: str
    scope_ref: str
    candidate_ref: str
    check_ref: str
    response_ref: str
    source: str
    status: str
    checked_at: str
    expires_at: str
    evidence: str = ""

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value.strip()
            for field, value in vars(self).items()
            if field != "evidence"
        ) or not isinstance(self.evidence, str):
            raise ValueError("self-check observation fields must be nonempty strings")
        if self.status not in {"passed", "failed"}:
            raise ValueError("invalid self-check status")
        if _timestamp(self.checked_at) >= _timestamp(self.expires_at):
            raise ValueError("self-check expiry must follow the observation")

    @property
    def key(self) -> ObservationKey:
        return self.task_id, self.check_id, self.subject_id, self.environment_ref

    def current(self, now: datetime) -> bool:
        return _timestamp(self.checked_at) <= now < _timestamp(self.expires_at)


class Cache:
    def __init__(self, workspace: Path, run_id: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise ValueError("invalid self-check Run ID")
        key = hashlib.sha256(os.fsencode(workspace.resolve())).hexdigest()
        self.base = Path(tempfile.gettempdir()).resolve()
        self.parts = (f"lbkit-{os.getuid()}", key)
        self.name = f"{run_id}.observations.json"

    @contextmanager
    def _directory(self, *, create: bool) -> Iterator[int]:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open(self.base, flags)
        try:
            for part in self.parts:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = child
                info = os.fstat(fd)
                if info.st_uid != os.getuid() or info.st_mode & 0o077:
                    raise PermissionError("self-check cache directory is not private")
            yield fd
        finally:
            os.close(fd)

    def _read(
        self, directory: int
    ) -> tuple[bytes | None, dict[ObservationKey, Observation]]:
        try:
            fd = os.open(
                self.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=directory,
            )
        except FileNotFoundError:
            return None, {}
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
            ):
                raise PermissionError("self-check cache file is not private")
            raw = handle.read(MAX_CACHE_BYTES + 1)
        if len(raw) > MAX_CACHE_BYTES:
            raise ValueError("self-check cache exceeds the size limit")
        try:
            entries = json.loads(raw, object_pairs_hook=state.unique_object)
            if not isinstance(entries, list):
                raise ValueError("self-check cache must be a list")
            rows = [Observation(**entry) for entry in entries]
            result = {row.key: row for row in rows}
            if len(result) != len(rows):
                raise ValueError("duplicate self-check observations")
        except (TypeError, ValueError, RecursionError):
            return raw, {}
        return raw, result

    def get(
        self,
        key: ObservationKey,
        *,
        scope_ref: str,
        candidate_ref: str,
        check_ref: str,
        now: datetime,
    ) -> Observation | None:
        try:
            with self._directory(create=False) as directory:
                _, entries = self._read(directory)
        except (OSError, ValueError):
            return None
        row = entries.get(key)
        if (
            row is not None
            and row.scope_ref == scope_ref
            and row.candidate_ref == candidate_ref
            and row.check_ref == check_ref
            and row.current(now)
        ):
            return row
        return None

    def record(self, row: Observation, *, now: datetime | None = None) -> bool:
        """Store an already verified reply. Keep newer replies and original expiry."""
        now = datetime.now(timezone.utc) if now is None else now
        if not row.current(now):
            return False
        try:
            with self._directory(create=True) as directory:
                fcntl.flock(directory, fcntl.LOCK_EX)
                raw, entries = self._read(directory)
                prior = entries.get(row.key)
                if prior is not None and (
                    prior.response_ref == row.response_ref
                    or _timestamp(prior.checked_at) >= _timestamp(row.checked_at)
                ):
                    return False
                entries = {
                    key: item for key, item in entries.items() if item.current(now)
                }
                entries[row.key] = row
                value = json.dumps(
                    [asdict(entries[key]) for key in sorted(entries)], sort_keys=True
                ).encode()
                if len(value) > MAX_CACHE_BYTES:
                    raise ValueError("self-check cache exceeds the size limit")
                replace_bytes_at(directory, self.name, value, raw)
        except (OSError, ValueError) as exc:
            raise LbError(f"self-check cache unavailable: {exc}", EXIT_REFUSED) from exc
        return True
