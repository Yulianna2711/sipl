from __future__ import annotations

from typing import Callable, Mapping

from .. import ast
from ..parser import parse
from .errors import SiplRuntimeError, StepLimitExceeded, UndefinedVariableError
from .events import (AfterStatement, BeforeStatement, ConditionEvaluated, Event,
                     ProgramFinished, ProgramStarted, VariableChanged)

State = dict[str, int]
Listener = Callable[[Event], None]

DEFAULT_MAX_STEPS = 100_000


class Interpreter:
    def __init__(self, initial: Mapping[str, int] | None = None,
                 max_steps: int = DEFAULT_MAX_STEPS,
                 listener: Listener | None = None):
        self.state: State = dict(initial or {})
        self.max_steps = max_steps
        self.steps = 0
        self.listener = listener

    def _emit(self, event: Event) -> None:
        if self.listener is not None:
            self.listener(event)

    def _snapshot(self) -> State:
        return dict(self.state)

    def _tick(self, node) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise StepLimitExceeded(self.max_steps, node.span)

    def eval_aexp(self, e: ast.AExp) -> int:
        if isinstance(e, ast.Num):
            return e.value
        if isinstance(e, ast.Var):
            try:
                return self.state[e.name]
            except KeyError:
                raise UndefinedVariableError(e.name, e.span) from None
        if isinstance(e, ast.Add):
            return self.eval_aexp(e.left) + self.eval_aexp(e.right)
        if isinstance(e, ast.Sub):
            return self.eval_aexp(e.left) - self.eval_aexp(e.right)
        if isinstance(e, ast.Mul):
            return self.eval_aexp(e.left) * self.eval_aexp(e.right)
        raise TypeError(f"not an arithmetic expression: {e!r}")

    def eval_bexp(self, b: ast.BExp) -> bool:
        if isinstance(b, ast.Eq):
            return self.eval_aexp(b.left) == self.eval_aexp(b.right)
        if isinstance(b, ast.Gt):
            return self.eval_aexp(b.left) > self.eval_aexp(b.right)
        if isinstance(b, ast.Or):
            return self.eval_bexp(b.left) or self.eval_bexp(b.right)
        if isinstance(b, ast.Not):
            return not self.eval_bexp(b.operand)
        raise TypeError(f"not a condition: {b!r}")

    def _check(self, kind: str, cond: ast.BExp) -> bool:
        result = self.eval_bexp(cond)
        self._emit(ConditionEvaluated(self.steps, kind, result, cond.span))
        return result

    def exec_stmt(self, s: ast.Stmt) -> None:
        if isinstance(s, ast.Seq):
            for stmt in s.stmts:
                self.exec_stmt(stmt)
            return

        if isinstance(s, ast.Skip):
            kind = "skip"
        elif isinstance(s, ast.Assign):
            kind = "assign"
        elif isinstance(s, ast.If):
            kind = "if"
        elif isinstance(s, ast.While):
            kind = "while"
        else:
            raise TypeError(f"not a statement: {s!r}")

        self._emit(BeforeStatement(self.steps, kind, s.span, self._snapshot()))
        if kind == "skip":
            self._tick(s)
        elif kind == "assign":
            self._tick(s)
            value = self.eval_aexp(s.expr)
            old = self.state.get(s.target)
            self.state[s.target] = value
            self._emit(VariableChanged(self.steps, s.target, old, value, s.span))
        elif kind == "if":
            self._tick(s)
            branch = s.then_branch if self._check("if", s.cond) else s.else_branch
            self.exec_stmt(branch)
        else:
            while True:
                self._tick(s)
                if not self._check("while", s.cond):
                    break
                self.exec_stmt(s.body)
        self._emit(AfterStatement(self.steps, kind, s.span, self._snapshot()))

    def run(self, program: ast.Program) -> State:
        self._emit(ProgramStarted(self.steps, self._snapshot()))
        try:
            self.exec_stmt(program.body)
        except SiplRuntimeError as err:
            status = "step_limit" if isinstance(err, StepLimitExceeded) else "error"
            self._emit(ProgramFinished(self.steps, status, self._snapshot(),
                                       err.message, err.span))
            raise
        self._emit(ProgramFinished(self.steps, "ok", self._snapshot()))
        return self._snapshot()


def run(program: ast.Program | str,
        initial: Mapping[str, int] | None = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        listener: Listener | None = None) -> State:
    if isinstance(program, str):
        program = parse(program)
    return Interpreter(initial, max_steps, listener).run(program)