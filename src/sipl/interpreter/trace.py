from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .. import ast
from ..parser import parse
from .errors import SiplRuntimeError
from .events import Event, ProgramFinished
from .interpreter import DEFAULT_MAX_STEPS, Interpreter


@dataclass(frozen=True)
class Trace:
    events: tuple[Event, ...]

    @property
    def finished(self) -> ProgramFinished:
        return self.events[-1]

    @property
    def status(self) -> str:
        return self.finished.status

    @property
    def final_state(self) -> dict:
        return dict(self.finished.state)

    def of_type(self, event_type: str) -> list[Event]:
        return [e for e in self.events if e.type == event_type]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "final_state": self.final_state,
            "events": [e.to_dict() for e in self.events],
        }


def trace(program: ast.Program | str,
          initial: Mapping[str, int] | None = None,
          max_steps: int = DEFAULT_MAX_STEPS) -> Trace:
    if isinstance(program, str):
        program = parse(program)
    events: list[Event] = []
    try:
        Interpreter(initial, max_steps, events.append).run(program)
    except SiplRuntimeError:
        pass
    return Trace(tuple(events))