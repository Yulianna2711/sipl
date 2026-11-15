from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass

BASIC_FUNCTIONS = ("add", "sub", "mult", "or", "neg", "eq", "gr")


@dataclass(frozen=True)
class Const:
    value: int


@dataclass(frozen=True)
class Deref:
    name: str

@dataclass(frozen=True)
class Basic:
    name: str

    def __post_init__(self) -> None:
        if self.name not in BASIC_FUNCTIONS:
            raise ValueError(f"unknown base function {self.name!r}; "
                             f"expected one of {BASIC_FUNCTIONS}")


@dataclass(frozen=True)
class Super:
    func: Basic
    args: tuple["Term", ...]

    @property
    def n(self) -> int:
        return len(self.args)


@dataclass(frozen=True)
class AS:
    name: str
    func: "Term"


@dataclass(frozen=True)
class Comp:
    left: "Term"
    right: "Term"


@dataclass(frozen=True)
class IF:
    cond: "Term"
    then_term: "Term"
    else_term: "Term"


@dataclass(frozen=True)
class WH:
    cond: "Term"
    body: "Term"


@dataclass(frozen=True)
class Id:
   pass

Term = Const | Deref | Super | AS | Comp | IF | WH | Id

def term_to_dict(term):
    if isinstance(term, tuple):
        return [term_to_dict(t) for t in term]
    if is_dataclass(term):
        data = {"type": type(term).__name__}
        for f in fields(term):
            data[f.name] = term_to_dict(getattr(term, f.name))
        return data
    return term