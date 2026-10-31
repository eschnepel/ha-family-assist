from __future__ import annotations

import asyncio
from collections import deque


class Ticket:
    def __init__(self) -> None:
        self.granted = asyncio.Event()
        self.moved = asyncio.Event()


class GenerationQueue:
    """FIFO queue limiting concurrent generations; unlimited when disabled."""

    def __init__(self, enabled: bool = True, parallel: int = 1):
        self.enabled = enabled
        self.parallel = max(1, parallel)
        self._waiting: deque[Ticket] = deque()
        self._running = 0

    @property
    def running(self) -> int:
        return self._running

    @property
    def waiting(self) -> int:
        return len(self._waiting)

    def enqueue(self) -> Ticket:
        ticket = Ticket()
        if not self.enabled or (self._running < self.parallel and not self._waiting):
            self._running += 1
            ticket.granted.set()
        else:
            self._waiting.append(ticket)
        return ticket

    def position(self, ticket: Ticket) -> int:
        """1-based position among waiting tickets, 0 when granted."""
        try:
            return list(self._waiting).index(ticket) + 1
        except ValueError:
            return 0

    def release(self, ticket: Ticket) -> None:
        if ticket in self._waiting:
            self._waiting.remove(ticket)
            self._notify()
            return
        if ticket.granted.is_set():
            self._running -= 1
            self._dispatch()

    def _dispatch(self) -> None:
        while self._waiting and (not self.enabled or self._running < self.parallel):
            ticket = self._waiting.popleft()
            self._running += 1
            ticket.granted.set()
            ticket.moved.set()
        self._notify()

    def _notify(self) -> None:
        for ticket in self._waiting:
            ticket.moved.set()
