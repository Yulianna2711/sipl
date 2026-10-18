from __future__ import annotations

from ..ast import SourceSpan


class SiplRuntimeError(Exception):
    def __init__(self, message: str, span: SourceSpan | None = None):
        self.message = message
        self.span = span
        where = f" (at {span})" if span is not None else ""
        super().__init__(f"{message}{where}")


class UndefinedVariableError(SiplRuntimeError):
    def __init__(self, name: str, span: SourceSpan | None = None):
        self.name = name
        super().__init__(f"variable '{name}' is not defined", span)


class StepLimitExceeded(SiplRuntimeError):
    def __init__(self, limit: int, span: SourceSpan | None = None):
        self.limit = limit
        super().__init__(f"step limit of {limit} exceeded (possible infinite loop)", span)