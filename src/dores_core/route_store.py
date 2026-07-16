"""Route storage primitives."""

import threading
from dataclasses import dataclass, field
from typing import Protocol

from .types import JSONDict


class RouteStore(Protocol):
    def set_session_route(self, session_id: str, route: JSONDict) -> None:
        """Persist a session route."""

    def get_session_route(self, session_id: str) -> JSONDict | None:
        """Return a session route."""


@dataclass
class InMemoryRouteStore:
    _session_routes: dict[str, JSONDict] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set_session_route(self, session_id: str, route: JSONDict) -> None:
        if not session_id:
            return
        with self._lock:
            self._session_routes[session_id] = route.copy()

    def get_session_route(self, session_id: str) -> JSONDict | None:
        if not session_id:
            return None
        with self._lock:
            data = self._session_routes.get(session_id)
            if data is None:
                return None
            return data.copy()
