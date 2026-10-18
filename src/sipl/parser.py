from __future__ import annotations

from importlib import resources
from pathlib import Path

from lark import Lark, Token, Transformer, v_args
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedToken

from . import ast
from .diagnostics import Diagnostic, SiplSyntaxError, pretty_token


def _span(meta) -> ast.SourceSpan:
    return ast.SourceSpan(meta.line, meta.column, meta.end_line, meta.end_column)


def _tok_span(tok: Token) -> ast.SourceSpan:
    return ast.SourceSpan(tok.line, tok.column, tok.end_line, tok.end_column)


@v_args(meta=True, inline=True)
class _ToAst(Transformer):
    def program(self, meta, body):
        return ast.Program(body, _span(meta))

    def seq(self, meta, *stmts):
        return ast.Seq(tuple(stmts), _span(meta))

    def assign(self, meta, name, expr):
        return ast.Assign(str(name), expr, _span(meta))

    def if_stmt(self, meta, cond, then_branch, else_branch):
        return ast.If(cond, then_branch, else_branch, _span(meta))

    def while_stmt(self, meta, cond, body):
        return ast.While(cond, body, _span(meta))

    def block(self, meta, body):
        return body

    def skip(self, meta):
        return ast.Skip(_span(meta))

    def add(self, meta, a, b):
        return ast.Add(a, b, _span(meta))

    def sub(self, meta, a, b):
        return ast.Sub(a, b, _span(meta))

    def mul(self, meta, a, b):
        return ast.Mul(a, b, _span(meta))

    def num(self, meta, tok):
        return ast.Num(int(tok), _tok_span(tok))

    def var(self, meta, tok):
        return ast.Var(str(tok), _tok_span(tok))

    def eq(self, meta, a, b):
        return ast.Eq(a, b, _span(meta))

    def gt(self, meta, a, b):
        return ast.Gt(a, b, _span(meta))

    def or_(self, meta, a, b):
        return ast.Or(a, b, _span(meta))

    def not_(self, meta, a):
        return ast.Not(a, _span(meta))


def _load_grammar() -> str:
    repo_copy = Path(__file__).resolve().parents[2] / "grammar" / "sipl.lark"
    if repo_copy.is_file():
        return repo_copy.read_text(encoding="utf-8")
    return (resources.files("sipl") / "_grammar" / "sipl.lark").read_text(encoding="utf-8")


_LARK = Lark(_load_grammar(), start="program", parser="lalr", propagate_positions=True)
_TRANSFORMER = _ToAst()


def _line_of(source: str, line: int) -> str:
    lines = source.splitlines()
    return lines[line - 1] if 1 <= line <= len(lines) else ""


def _diagnose(source: str, err: Exception) -> Diagnostic:
    if isinstance(err, UnexpectedCharacters):
        expected = tuple(sorted({pretty_token(t) for t in err.allowed or ()}))
        bad = source[err.pos_in_stream] if err.pos_in_stream is not None else "?"
        return Diagnostic(err.line, err.column, f"unexpected character {bad!r}",
                          expected, _line_of(source, err.line))
    if isinstance(err, UnexpectedToken):
        tok = err.token
        expected = tuple(sorted({pretty_token(t) for t in err.expected}))
        if tok.type == "$END":
            line = source.count("\n") + 1
            col = len(_line_of(source, line)) + 1
            return Diagnostic(line, col, "unexpected end of input", expected,
                              _line_of(source, line))
        return Diagnostic(tok.line, tok.column, f"unexpected {str(tok)!r}", expected,
                          _line_of(source, tok.line))
    if isinstance(err, UnexpectedEOF):
        line = source.count("\n") + 1
        col = len(_line_of(source, line)) + 1
        expected = tuple(sorted({pretty_token(str(t)) for t in err.expected}))
        return Diagnostic(line, col, "unexpected end of input", expected,
                          _line_of(source, line))
    return Diagnostic(1, 1, str(err))


def parse(source: str) -> ast.Program:
    try:
        tree = _LARK.parse(source)
    except (UnexpectedCharacters, UnexpectedToken, UnexpectedEOF) as err:
        raise SiplSyntaxError(_diagnose(source, err)) from None
    return _TRANSFORMER.transform(tree)