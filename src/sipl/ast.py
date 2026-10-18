from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSpan:
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    def __str__(self) -> str:
        return f"{self.start_line}:{self.start_column}-{self.end_line}:{self.end_column}"

@dataclass(frozen=True)
class Num:
    value: int
    span: SourceSpan


@dataclass(frozen=True)
class Var:
    name: str
    span: SourceSpan


@dataclass(frozen=True)
class Add:
    left: "AExp"
    right: "AExp"
    span: SourceSpan


@dataclass(frozen=True)
class Sub:
    left: "AExp"
    right: "AExp"
    span: SourceSpan


@dataclass(frozen=True)
class Mul:
    left: "AExp"
    right: "AExp"
    span: SourceSpan


AExp = Num | Var | Add | Sub | Mul

@dataclass(frozen=True)
class Eq:
    left: AExp
    right: AExp
    span: SourceSpan


@dataclass(frozen=True)
class Gt:
    left: AExp
    right: AExp
    span: SourceSpan


@dataclass(frozen=True)
class Or:
    left: "BExp"
    right: "BExp"
    span: SourceSpan


@dataclass(frozen=True)
class Not:
    operand: "BExp"
    span: SourceSpan


BExp = Eq | Gt | Or | Not

@dataclass(frozen=True)
class Assign:
    target: str
    expr: AExp
    span: SourceSpan


@dataclass(frozen=True)
class Seq:
    stmts: tuple["Stmt", ...]
    span: SourceSpan


@dataclass(frozen=True)
class If:
    cond: BExp
    then_branch: "Stmt"
    else_branch: "Stmt"
    span: SourceSpan


@dataclass(frozen=True)
class While:
    cond: BExp
    body: "Stmt"
    span: SourceSpan


@dataclass(frozen=True)
class Skip:
    span: SourceSpan


Stmt = Assign | Seq | If | While | Skip


@dataclass(frozen=True)
class Program:
    body: Stmt
    span: SourceSpan