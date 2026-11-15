from __future__ import annotations

from dataclasses import dataclass

from .. import ast
from ..parser import parse
from .terms import AS, IF, WH, Basic, Comp, Const, Deref, Id, Super, Term


@dataclass(frozen=True)
class RuleStep:
    rule: str
    span: ast.SourceSpan
    term: Term


class _Builder:
    def __init__(self, record: bool = False):
        self.steps: list[RuleStep] | None = [] if record else None

    def _rule(self, rule: str, span: ast.SourceSpan, build) -> Term:
        if self.steps is None:
            return build()
        slot = len(self.steps)
        self.steps.append(None)
        term = build()
        self.steps[slot] = RuleStep(rule, span, term)
        return term

    def sem_P(self, program: ast.Program) -> Term:
        return self._rule("NS_Prog", program.span, lambda: self.sem_S(program.body))

    def sem_S(self, s: ast.Stmt) -> Term:
        if isinstance(s, ast.Assign):
            return self._rule("NS_Stm_As", s.span,
                              lambda: AS(s.target, self.sem_A(s.expr)))
        if isinstance(s, ast.Seq):
            return self._seq(s.stmts)
        if isinstance(s, ast.If):
            return self._rule("NS_Stm_If", s.span, lambda: IF(
                self.sem_B(s.cond), self.sem_S(s.then_branch), self.sem_S(s.else_branch)))
        if isinstance(s, ast.While):
            return self._rule("NS_Stm_Wh", s.span,
                              lambda: WH(self.sem_B(s.cond), self.sem_S(s.body)))
        if isinstance(s, ast.Skip):
            return self._rule("NS_Stm_skip", s.span, Id)
        raise TypeError(f"not a statement: {s!r}")

    def _seq(self, stmts: tuple[ast.Stmt, ...]) -> Term:
        if len(stmts) == 1:
            return self.sem_S(stmts[0])
        first, last = stmts[0].span, stmts[-1].span
        span = ast.SourceSpan(first.start_line, first.start_column,
                              last.end_line, last.end_column)
        return self._rule("NS_Stm_Seq", span, lambda: Comp(
            self._seq(stmts[:-1]), self.sem_S(stmts[-1])))

    def sem_A(self, a: ast.AExp) -> Term:
        if isinstance(a, ast.Num):
            return self._rule("NS_A_Num", a.span, lambda: Const(a.value))
        if isinstance(a, ast.Var):
            return self._rule("NS_A_Var", a.span, lambda: Deref(a.name))
        for node_type, rule, name in ((ast.Add, "NS_A_Add", "add"),
                                      (ast.Sub, "NS_A_Sub", "sub"),
                                      (ast.Mul, "NS_A_Mult", "mult")):
            if isinstance(a, node_type):
                return self._rule(rule, a.span, lambda: Super(
                    Basic(name), (self.sem_A(a.left), self.sem_A(a.right))))
        raise TypeError(f"not an arithmetic expression: {a!r}")

    def sem_B(self, b: ast.BExp) -> Term:
        if isinstance(b, ast.Eq):
            return self._rule("NS_B_eq", b.span, lambda: Super(
                Basic("eq"), (self.sem_A(b.left), self.sem_A(b.right))))
        if isinstance(b, ast.Gt):
            return self._rule("NS_B_gr", b.span, lambda: Super(
                Basic("gr"), (self.sem_A(b.left), self.sem_A(b.right))))
        if isinstance(b, ast.Or):
            return self._rule("NS_B_or", b.span, lambda: Super(
                Basic("or"), (self.sem_B(b.left), self.sem_B(b.right))))
        if isinstance(b, ast.Not):
            return self._rule("NS_B_neg", b.span, lambda: Super(
                Basic("neg"), (self.sem_B(b.operand),)))
        raise TypeError(f"not a condition: {b!r}")


def sem_P(program: ast.Program) -> Term:
    return _Builder().sem_P(program)


def sem_S(stmt: ast.Stmt) -> Term:
    return _Builder().sem_S(stmt)


def sem_A(expr: ast.AExp) -> Term:
    return _Builder().sem_A(expr)


def sem_B(cond: ast.BExp) -> Term:
    return _Builder().sem_B(cond)

def term_of(program: ast.Program | str) -> Term:
    if isinstance(program, str):
        program = parse(program)
    return sem_P(program)


def explain(program: ast.Program | str) -> list[RuleStep]:
    if isinstance(program, str):
        program = parse(program)
    builder = _Builder(record=True)
    builder.sem_P(program)
    return builder.steps