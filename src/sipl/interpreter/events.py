from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ..ast import SourceSpan


def span_to_dict(span: SourceSpan | None) -> dict | None:
    if span is None:
        return None
    return {
        "start_line": span.start_line,
        "start_column": span.start_column,
        "end_line": span.end_line,
        "end_column": span.end_column,
    }


@dataclass(frozen=True)
class Event:
    type: ClassVar[str] = "event"
    step: int

    def _payload(self) -> dict:
        return {}

    def to_dict(self) -> dict:
        return {"type": self.type, "step": self.step, **self._payload()}


@dataclass(frozen=True)
class ProgramStarted(Event):
    type: ClassVar[str] = "program_started"
    state: dict

    def _payload(self) -> dict:
        return {"state": dict(self.state)}


@dataclass(frozen=True)
class BeforeStatement(Event):
    type: ClassVar[str] = "before_statement"
    kind: str
    span: SourceSpan
    state: dict

    def _payload(self) -> dict:
        return {"kind": self.kind, "span": span_to_dict(self.span), "state": dict(self.state)}


@dataclass(frozen=True)
class AfterStatement(Event):
    type: ClassVar[str] = "after_statement"
    kind: str
    span: SourceSpan
    state: dict

    def _payload(self) -> dict:
        return {"kind": self.kind, "span": span_to_dict(self.span), "state": dict(self.state)}


@dataclass(frozen=True)
class VariableChanged(Event):
    type: ClassVar[str] = "variable_changed"
    name: str
    old: int | None
    new: int
    span: SourceSpan

    def _payload(self) -> dict:
        return {"name": self.name, "old": self.old, "new": self.new,
                "span": span_to_dict(self.span)}


@dataclass(frozen=True)
class ConditionEvaluated(Event):
    type: ClassVar[str] = "condition_evaluated"
    kind: str
    result: bool
    span: SourceSpan

    def _payload(self) -> dict:
        return {"kind": self.kind, "result": self.result, "span": span_to_dict(self.span)}


@dataclass(frozen=True)
class ProgramFinished(Event):
    type: ClassVar[str] = "program_finished"
    status: str
    state: dict
    error: str | None = None
    error_span: SourceSpan | None = None

    def _payload(self) -> dict:
        data = {"status": self.status, "state": dict(self.state)}
        if self.error is not None:
            data["error"] = self.error
            data["error_span"] = span_to_dict(self.error_span)
        return data