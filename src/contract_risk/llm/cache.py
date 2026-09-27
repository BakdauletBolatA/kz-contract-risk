"""Кэш ответов LLM: повторный прогон eval даёт те же находки и не стоит денег.

Ключ — sha256 от модели, версии промпта, системного промпта и сообщения
пользователя. Смена любого из них — промах кэша и новый вызов, поэтому
прогон со старым промптом нельзя случайно выдать за прогон с новым.
Хранится в SQLite (stdlib): один файл, атомарные записи, безопасно для
параллельных потоков.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path


def cache_key(model: str, prompt_version: str, system: str, user: str) -> str:
    h = hashlib.sha256()
    for part in (model, prompt_version, system, user):
        h.update(part.encode())
        h.update(b"\x00")
    return h.hexdigest()


class ResponseCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS responses ("
            "key TEXT PRIMARY KEY, model TEXT, prompt_version TEXT, payload TEXT, created_at TEXT)"
        )
        self._conn.commit()

    def get(self, key: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM responses WHERE key = ?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, model: str, prompt_version: str, payload: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO responses VALUES (?, ?, ?, ?, ?)",
                (
                    key,
                    model,
                    prompt_version,
                    json.dumps(payload, ensure_ascii=False),
                    datetime.now(UTC).isoformat(timespec="seconds"),
                ),
            )
            self._conn.commit()

    def __len__(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT count(*) FROM responses").fetchone()[0])
