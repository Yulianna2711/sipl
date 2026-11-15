from __future__ import annotations

from .terms import AS, IF, WH, Basic, Comp, Const, Deref, Id, Super, Term

STYLES = ("course", "ascii")

_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def format_term(term: Term, style: str = "course") -> str:
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}; expected one of {STYLES}")
    return _fmt(term, style == "course")


def _fmt(t, unicode: bool) -> str:
    if isinstance(t, Const):
        return str(t.value)
    if isinstance(t, Deref):
        return t.name + ("⇒" if unicode else "=>")
    if isinstance(t, Basic):
        return t.name
    if isinstance(t, Super):
        power = str(t.n).translate(_SUPERSCRIPT) if unicode else str(t.n)
        parts = [t.func.name, *(_fmt(a, unicode) for a in t.args)]
        return f"S{power}({', '.join(parts)})"
    if isinstance(t, AS):
        return f"AS_{t.name}({_fmt(t.func, unicode)})"
    if isinstance(t, Comp):
        dot = " · " if unicode else " ; "
        left = _fmt(t.left, unicode)
        right = _fmt(t.right, unicode)
        if isinstance(t.right, Comp):
            right = f"({right})"
        return left + dot + right
    if isinstance(t, IF):
        return f"IF({_fmt(t.cond, unicode)}, {_fmt(t.then_term, unicode)}, {_fmt(t.else_term, unicode)})"
    if isinstance(t, WH):
        return f"WH({_fmt(t.cond, unicode)}, {_fmt(t.body, unicode)})"
    if isinstance(t, Id):
        return "id"
    raise TypeError(f"not a term: {t!r}")