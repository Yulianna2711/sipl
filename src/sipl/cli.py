from __future__ import annotations

import argparse
import json
import re
import sys
from importlib import metadata
from typing import TextIO

from .diagnostics import SiplSyntaxError
from .interpreter import (DEFAULT_MAX_STEPS, Interpreter, SiplRuntimeError,
                          StepLimitExceeded, trace)
from .interpreter.events import span_to_dict
from .parser import parse
from .serialize import ast_to_dict, format_tree

EXIT_OK = 0
EXIT_SYNTAX = 1
EXIT_USAGE = 2
EXIT_RUNTIME = 3

SCHEMA_VERSION = 1

_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


class _UsageError(Exception):
    pass

def _version() -> str:
    try:
        return metadata.version("sipl")
    except metadata.PackageNotFoundError:
        return "unknown"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sipl", description="Toolkit for the SIPL language.")
    parser.add_argument("--version", action="version", version=f"sipl {_version()}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def add(name: str, help_text: str, runnable: bool) -> None:
        sp = sub.add_parser(name, help=help_text, description=help_text)
        sp.add_argument("file", help="SIPL source file, or '-' to read stdin")
        sp.add_argument("--json", action="store_true",
                        help="print one JSON document instead of text")
        if runnable:
            sp.add_argument("--set", action="append", default=[], metavar="VAR=INT",
                            help="initial value of a variable (repeatable)")
            sp.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                            metavar="N", help=f"step limit (default {DEFAULT_MAX_STEPS})")

    add("parse", "Parse a program and print its AST.", False)
    add("check", "Check the syntax of a program.", False)
    add("run", "Run a program and print the final state.", True)
    add("trace", "Run a program and print its execution trace.", True)
    return parser

def _dump(out: TextIO, payload: dict) -> None:
    out.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _envelope(command: str, ok: bool, **fields) -> dict:
    return {"schema_version": SCHEMA_VERSION, "command": command, "ok": ok, **fields}


def _state_text(state: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(state.items())) or "(empty)"


def _fail(args, out: TextIO, err: TextIO, kind: str, message: str,
          code: int, text: str | None = None, **extra) -> int:
    if args.json:
        _dump(out, _envelope(args.command, False,
                             error={"kind": kind, "message": message, **extra}))
    else:
        print(text if text is not None else message, file=err)
    return code


def _syntax_failure(args, out, err, exc: SiplSyntaxError) -> int:
    d = exc.diagnostic
    return _fail(args, out, err, "syntax", d.message, EXIT_SYNTAX,
                 text=d.format(), line=d.line, column=d.column,
                 expected=list(d.expected))

def _read_source(args) -> str:
    if args.file == "-":
        return sys.stdin.read()
    with open(args.file, encoding="utf-8") as handle:
        return handle.read()


def _parse_initial(items: list[str]) -> dict[str, int]:
    state: dict[str, int] = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep or not _IDENT.fullmatch(name):
            raise _UsageError(f"bad --set value {item!r}, expected VAR=INT")
        try:
            state[name] = int(value)
        except ValueError:
            raise _UsageError(f"bad --set value {item!r}, expected VAR=INT") from None
    return state

def _format_event(e: dict) -> str:
    kind = e["type"]
    if kind == "program_started":
        return f"start          {_state_text(e['state'])}"
    if kind == "before_statement":
        s = e["span"]
        return f"before {e['kind']:<8}[{s['start_line']}:{s['start_column']}]  {_state_text(e['state'])}"
    if kind == "after_statement":
        s = e["span"]
        return f"after  {e['kind']:<8}[{s['start_line']}:{s['start_column']}]  {_state_text(e['state'])}"
    if kind == "variable_changed":
        old = "undefined" if e["old"] is None else e["old"]
        return f"    {e['name']}: {old} -> {e['new']}"
    if kind == "condition_evaluated":
        s = e["span"]
        return f"    {e['kind']} condition [{s['start_line']}:{s['start_column']}] is {e['result']}"
    if kind == "program_finished":
        line = f"finished: {e['status']}  {_state_text(e['state'])}"
        if "error" in e:
            line += f"\nerror: {e['error']}"
        return line
    return kind

def _cmd_parse(args, source, out, err) -> int:
    data = ast_to_dict(parse(source))
    if args.json:
        _dump(out, _envelope("parse", True, ast=data))
    else:
        print(format_tree(data), file=out)
    return EXIT_OK


def _cmd_check(args, source, out, err) -> int:
    parse(source)
    if args.json:
        _dump(out, _envelope("check", True, file=args.file))
    else:
        print(f"OK: {args.file}", file=out)
    return EXIT_OK


def _cmd_run(args, source, out, err) -> int:
    program = parse(source)
    interp = Interpreter(_parse_initial(args.set), args.max_steps)
    try:
        interp.run(program)
    except SiplRuntimeError as exc:
        kind = "step_limit" if isinstance(exc, StepLimitExceeded) else "runtime"
        if args.json:
            _dump(out, _envelope("run", False, steps=interp.steps,
                                 state=dict(interp.state),
                                 error={"kind": kind, "message": exc.message,
                                        "span": span_to_dict(exc.span)}))
        else:
            print(f"Runtime error: {exc}", file=err)
        return EXIT_RUNTIME
    state = dict(interp.state)
    if args.json:
        _dump(out, _envelope("run", True, steps=interp.steps, final_state=state))
    else:
        for name, value in sorted(state.items()):
            print(f"{name} = {value}", file=out)
    return EXIT_OK


def _cmd_trace(args, source, out, err) -> int:
    result = trace(parse(source), _parse_initial(args.set), args.max_steps)
    ok = result.status == "ok"
    if args.json:
        extra = {}
        if not ok:
            fin = result.finished
            extra["error"] = {
                "kind": "step_limit" if result.status == "step_limit" else "runtime",
                "message": fin.error,
                "span": span_to_dict(fin.error_span),
            }
        _dump(out, _envelope("trace", ok, **result.to_dict(), **extra))
    else:
        for event in result.events:
            print(_format_event(event.to_dict()), file=out)
    return EXIT_OK if ok else EXIT_RUNTIME


_COMMANDS = {"parse": _cmd_parse, "check": _cmd_check,
             "run": _cmd_run, "trace": _cmd_trace}


def main(argv: list[str] | None = None, stdout: TextIO | None = None,
         stderr: TextIO | None = None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE

    try:
        source = _read_source(args)
    except (OSError, UnicodeDecodeError) as exc:
        return _fail(args, out, err, "io", f"cannot read {args.file!r}: {exc}",
                     EXIT_USAGE)
    try:
        return _COMMANDS[args.command](args, source, out, err)
    except SiplSyntaxError as exc:
        return _syntax_failure(args, out, err, exc)
    except _UsageError as exc:
        return _fail(args, out, err, "usage", str(exc), EXIT_USAGE)