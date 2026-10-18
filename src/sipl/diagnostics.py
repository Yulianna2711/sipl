from __future__ import annotations

from dataclasses import dataclass

TOKEN_NAMES = {
    "VAR": "variable name",
    "NUMBER": "number",
    "_ASSIGN": "':='",
    "_SEMI": "';'",
    "_PLUS": "'+'",
    "_MINUS": "'-'",
    "_STAR": "'*'",
    "_EQ": "'='",
    "_GT": "'>'",
    "_LP": "'('",
    "_RP": "')'",
    "_NOT": "'not'",
    "_OR": "'or'",
    "_BEGIN": "'begin'",
    "_END": "'end'",
    "_IF": "'if'",
    "_THEN": "'then'",
    "_ELSE": "'else'",
    "_WHILE": "'while'",
    "_DO": "'do'",
    "_SKIP": "'skip'",
    "$END": "end of input",
}


def pretty_token(name: str) -> str:
    return TOKEN_NAMES.get(name, name)


@dataclass(frozen=True)
class Diagnostic:
    line: int
    column: int
    message: str
    expected: tuple[str, ...] = ()
    source_line: str = ""

    def format(self) -> str:
        head = f"Syntax error at line {self.line}, column {self.column}: {self.message}"
        parts = [head]
        if self.expected:
            parts.append("Expected: " + ", ".join(self.expected))
        if self.source_line:
            parts.append(self.source_line)
            parts.append(" " * (self.column - 1) + "^")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "expected": list(self.expected),
        }


class SiplSyntaxError(Exception):
    def __init__(self, diagnostic: Diagnostic):
        super().__init__(diagnostic.format())
        self.diagnostic = diagnostic