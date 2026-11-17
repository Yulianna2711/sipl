from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Union

from .. import ast
from ..parser import parse
from .builder import term_of
from .formatter import STYLES, format_term
from .terms import AS, IF, WH, Comp, Const, Deref, Id, Super, Term

DEFAULT_MAX_STEPS = 100_000

State = dict
Value = Union[int, bool, dict]

_BASE_FUNCTIONS = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mult": lambda a, b: a * b,
    "or": lambda a, b: a or b,
    "neg": lambda a: not a,
    "eq": lambda a, b: a == b,
    "gr": lambda a, b: a > b,
}

_FORMULA = {Const: "const", Deref: "AF_DNM", Super: "AF_S", AS: "AF_AS",
            Comp: "AF_SEQ", IF: "AF_IF", WH: "AF_WH", Id: "AF_ID"}

_STATE_FORMULAS = {"AF_AS", "AF_SEQ", "AF_IF", "AF_WH", "AF_ID"}


@dataclass(frozen=True)
class EvalStep:
    formula: str
    term: Term
    state: dict
    result: Value | None
    depth: int
    note: str = ""

    @property
    def finished(self) -> bool:
        return self.result is not None


@dataclass(frozen=True)
class Evaluation:
    status: str
    value: Value | None
    reason: str | None
    steps: tuple[EvalStep, ...]

    @property
    def defined(self) -> bool:
        return self.status == "defined"

    @property
    def final_state(self) -> dict | None:
        return self.value if isinstance(self.value, dict) else None

    def to_dict(self, style: str = "course") -> dict:
        return {
            "status": self.status,
            "final_state": self.final_state,
            "value": self.value,
            "reason": self.reason,
            "steps": [{
                "formula": s.formula,
                "term_text": format_term(s.term, style),
                "state": s.state,
                "result": s.result,
                "finished": s.finished,
                "depth": s.depth,
                "note": s.note,
            } for s in self.steps],
        }


class _Undefined(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _show(value) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


class _Evaluator:
    def __init__(self, max_steps: int, record: bool):
        self.max_steps = max_steps
        self.count = 0
        self.records: list[dict] | None = [] if record else None

    def _open(self, term: Term, state: dict, depth: int, formula: str | None = None):
        self.count += 1
        if self.count > self.max_steps:
            raise _Undefined(f"step limit of {self.max_steps} exceeded "
                             "(the loop may not terminate)")
        if self.records is None:
            return None
        record = {"formula": formula or _FORMULA[type(term)], "term": term,
                  "state": dict(state), "result": None, "depth": depth, "note": ""}
        self.records.append(record)
        return record

    @staticmethod
    def _close(record, result: Value, note: str = "") -> Value:
        if record is not None:
            record["result"] = result
            record["note"] = note
        return result

    def apply(self, term: Term, st: dict, depth: int = 0) -> Value:
        record = self._open(term, st, depth)

        if isinstance(term, Const):
            return self._close(record, term.value, f"{term.value}(st) = {term.value}")

        if isinstance(term, Deref):
            if term.name not in st:
                raise _Undefined(f"variable '{term.name}' is not defined")
            value = st[term.name]
            return self._close(record, value, f"st({term.name}) = {value}")

        if isinstance(term, Super):
            args = [self.apply(a, st, depth + 1) for a in term.args]
            value = _BASE_FUNCTIONS[term.func.name](*args)
            shown = ", ".join(_show(a) for a in args)
            return self._close(record, value, f"{term.func.name}({shown}) = {_show(value)}")

        if isinstance(term, AS):
            value = self.apply(term.func, st, depth + 1)
            new_state = dict(st)
            new_state[term.name] = value
            return self._close(record, new_state, f"st[{term.name} -> {value}]")

        if isinstance(term, Comp):
            middle = self.apply(term.left, st, depth + 1)
            return self._close(record, self.apply(term.right, middle, depth + 1))

        if isinstance(term, IF):
            condition = self.apply(term.cond, st, depth + 1)
            branch = term.then_term if condition else term.else_term
            which = "first" if condition else "second"
            result = self.apply(branch, st, depth + 1)
            return self._close(record, result,f"condition is {_show(condition)}: the {which} branch is applied")

        if isinstance(term, WH):
            current = st
            iterations = 0
            while True:
                condition = self.apply(term.cond, current, depth + 1)
                marker = self._open(term, current, depth + 1, "AF_WH")
                self._close(marker, current,
                            f"st{iterations}: condition is {_show(condition)}")
                if not condition:
                    break
                current = self.apply(term.body, current, depth + 1)
                iterations += 1
            return self._close(record, current, f"{iterations} iteration(s)")

        if isinstance(term, Id):
            return self._close(record, st, "id(st) = st")

        raise TypeError(f"not a term: {term!r}")


def _to_term(subject) -> Term:
    if isinstance(subject, str):
        return term_of(parse(subject))
    if isinstance(subject, ast.Program):
        return term_of(subject)
    return subject


def evaluate(subject: Term | ast.Program | str,
             state: Mapping[str, int] | None = None, *,
             max_steps: int = DEFAULT_MAX_STEPS,
             record: bool = True) -> Evaluation:
    term = _to_term(subject)
    evaluator = _Evaluator(max_steps, record)
    value: Value | None = None
    reason: str | None = None
    try:
        value = evaluator.apply(term, dict(state or {}))
    except _Undefined as exc:
        reason = exc.reason
    except RecursionError:
        reason = "the term is nested too deeply to be evaluated"
    steps = tuple(EvalStep(**rec) for rec in (evaluator.records or []))
    return Evaluation("defined" if reason is None else "undefined", value, reason, steps)


def format_state(state: dict, style: str = "course") -> str:
    arrow = "↦" if style == "course" else "->"
    return "[" + ", ".join(f"{k} {arrow} {v}" for k, v in state.items()) + "]"


def _format_value(value, style: str) -> str:
    if isinstance(value, dict):
        return format_state(value, style)
    return _show(value)


def format_trace(evaluation: Evaluation, style: str = "course", width: int = 60) -> str:
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}; expected one of {STYLES}")
    ellipsis = "…" if style == "course" else "..."
    lines = []
    for step in evaluation.steps:
        text = format_term(step.term, style)
        if len(text) > width:
            text = text[:width - len(ellipsis)] + ellipsis
        line = f"{'  ' * step.depth}{step.formula:<7}{text}"
        if step.formula in _STATE_FORMULAS:
            line += f"  at {format_state(step.state, style)}"
        result = "undefined" if not step.finished else _format_value(step.result, style)
        line += f"  =  {result}"
        if step.note:
            line += f"   ({step.note})"
        lines.append(line)
    return "\n".join(lines)