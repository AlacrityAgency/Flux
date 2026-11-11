"""In-process event log shared by the web UI (SSE), the WebSocket and the headless CLI."""
from __future__ import annotations

import threading
import time
from collections import deque


class EventBus:
    def __init__(self, size: int = 2000):
        self._items: deque = deque(maxlen=size)
        self._lock = threading.Lock()
        self._sequence = 0
        self._listeners = []

    def publish(self, kind: str, payload: dict | None = None) -> dict:
        with self._lock:
            self._sequence += 1
            item = {"sequence": self._sequence, "kind": kind, "payload": payload or {}, "time": time.time()}
            self._items.append(item)
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(item)
            except Exception:
                pass
        return item

    def subscribe(self, callback):
        with self._lock:
            self._listeners.append(callback)

    def after(self, sequence: int = 0, limit: int = 500) -> list[dict]:
        with self._lock:
            return [item for item in self._items if item["sequence"] > sequence][:limit]

    @property
    def sequence(self) -> int:
        return self._sequence

