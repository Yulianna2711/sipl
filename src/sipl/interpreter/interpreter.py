from __future__ import annotations

from typing import Mapping

from .. import ast
from ..parser import parse
from .errors import StepLimitExceeded, UndefinedVariableError

State = dict[str, int]

DEFAULT_MAX_STEPS = 100_000


class Interpreter:
    def __init__(self, initial: Mapping[str, int] | None = None,
                 max_steps: int = DEFAULT_MAX_STEPS):
        self.state: State = dict(initial or {})
        self.max_steps = max_steps
        self.steps = 0

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

    def exec_stmt(self, s: ast.Stmt) -> None:
        if isinstance(s, ast.Skip):
            self._tick(s)
        elif isinstance(s, ast.Assign):
            self._tick(s)
            self.state[s.target] = self.eval_aexp(s.expr)
        elif isinstance(s, ast.Seq):
            for stmt in s.stmts:
                self.exec_stmt(stmt)
        elif isinstance(s, ast.If):
            self._tick(s)
            branch = s.then_branch if self.eval_bexp(s.cond) else s.else_branch
            self.exec_stmt(branch)
        elif isinstance(s, ast.While):
            while True:
                self._tick(s)
                if not self.eval_bexp(s.cond):
                    break
                self.exec_stmt(s.body)
        else:
            raise TypeError(f"not a statement: {s!r}")

    def run(self, program: ast.Program) -> State:
        self.exec_stmt(program.body)
        return dict(self.state)


def run(program: ast.Program | str,
        initial: Mapping[str, int] | None = None,
        max_steps: int = DEFAULT_MAX_STEPS) -> State:
    if isinstance(program, str):
        program = parse(program)
    return Interpreter(initial, max_steps).run(program)