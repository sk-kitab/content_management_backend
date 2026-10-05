"""
Persistent cache: (category, raw_span_text) -> normalized_text.

This is the piece that makes the pipeline cheap on re-runs: once "Dr." or "$42.50" has been
normalized once, it's never sent to the LLM again — anywhere, in any title, forever (scoped
per category to avoid cross-category collisions, see Span.key() in detectors.py).

It is also the *editable* artifact the user asked for: open the JSON file, fix an entry by
hand, re-run the pipeline — no LLM call happens for that term again, and the fix applies
everywhere the term appears in future runs.

Decoupled behind an ABC so the backing store (flat JSON file today) can become a real DB table
later without touching pipeline.py.
"""
from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path


class NormalizationCache(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None: ...

    @abstractmethod
    def set(self, key: str, normalized_text: str) -> None: ...

    @abstractmethod
    def get_many(self, keys: list[str]) -> dict[str, str]: ...

    @abstractmethod
    def flush(self) -> None: ...


class JSONFileCache(NormalizationCache):
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, str] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text())
        self._dirty = False

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def get_many(self, keys: list[str]) -> dict[str, str]:
        return {k: self._data[k] for k in keys if k in self._data}

    def set(self, key: str, normalized_text: str) -> None:
        if self._data.get(key) != normalized_text:
            self._data[key] = normalized_text
            self._dirty = True

    def flush(self) -> None:
        if not self._dirty:
            return
        merged: dict[str, str] = {}
        if self.path.exists():
            try:
                on_disk = json.loads(self.path.read_text())
                if isinstance(on_disk, dict):
                    merged.update(on_disk)
            except (OSError, ValueError):
                pass
        merged.update(self._data)
        self._data = merged
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name + ".", suffix=".tmp")
        try:
            os.chmod(tmp, 0o644)
            with os.fdopen(fd, "w") as fh:
                fh.write(json.dumps(merged, indent=2, ensure_ascii=False, sort_keys=True))
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        self._dirty = False

    def __enter__(self) -> "JSONFileCache":
        return self

    def __exit__(self, *exc) -> None:
        self.flush()


class InMemoryCache(NormalizationCache):
    """Non-persistent cache for dry runs / tests — deliberately cannot pollute the real
    on-disk cache. Never use this for an actual generation run."""

    def __init__(self):
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def get_many(self, keys: list[str]) -> dict[str, str]:
        return {k: self._data[k] for k in keys if k in self._data}

    def set(self, key: str, normalized_text: str) -> None:
        self._data[key] = normalized_text

    def flush(self) -> None:
        pass
