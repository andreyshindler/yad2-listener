"""Persist the set of already-seen listing ids across runs."""

from __future__ import annotations

import json
import os
import tempfile


class SeenStore:
    """A JSON-backed set of listing ids we've already notified about."""

    def __init__(self, path: str):
        self.path = path
        self._ids: set[str] = self._load()

    def _load(self) -> set[str]:
        if not os.path.exists(self.path):
            return set()
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            return set(map(str, data.get("seen_ids", [])))
        except (json.JSONDecodeError, OSError):
            return set()

    def __contains__(self, listing_id: str) -> bool:
        return str(listing_id) in self._ids

    def __len__(self) -> int:
        return len(self._ids)

    def add(self, listing_id: str) -> None:
        self._ids.add(str(listing_id))

    def save(self) -> None:
        """Atomically write the state file."""
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"seen_ids": sorted(self._ids)}, fh, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
