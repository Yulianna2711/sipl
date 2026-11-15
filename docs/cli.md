# SIPL command line interface

```
sipl [--version] COMMAND ...
python -m sipl COMMAND ...       
```

## Commands

| Command | What it does |
|---------|--------------|
| `sipl parse FILE`  | Parse the program and print its AST. |
| `sipl check FILE`  | Check the syntax only. |
| `sipl run FILE`    | Run the program and print the final state. |
| `sipl trace FILE`  | Run the program and print the execution trace. |
| `sipl term FILE`   | Print the semantic term of the program. |

`FILE` is a SIPL source file, or `-` to read the program from stdin.

Options:

| Option | Commands | Meaning |
|--------|----------|---------|
| `--json` | all | Print one JSON document instead of text. |
| `--set VAR=INT` | run, trace | Initial value of a variable. Repeat for several variables. |
| `--max-steps N` | run, trace | Step limit against infinite loops (default 100000). |
| `--style course\|ascii` | term | Notation: unicode `course` (default) or plain `ascii`. |
| `--steps` | term | Also list the rules `NS_*` applied while building the term. |

Examples:

```
sipl check examples/power.sipl
sipl run examples/power.sipl --set X=2 --set Y=5
sipl trace examples/gcd.sipl --set M=12 --set N=18
sipl run examples/gcd.sipl --set M=12 --set N=18 --json
echo "begin X := 1 end" | sipl parse -
sipl term examples/power.sipl
sipl term examples/gcd.sipl --steps --style ascii
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success. |
| 1 | Syntax error in the SIPL source. |
| 2 | Usage or I/O error (bad option, unreadable file). |
| 3 | Runtime error (undefined variable, step limit exceeded). |

In text mode errors go to stderr. In `--json` mode errors are JSON on stdout
(argparse usage errors such as an unknown command are still plain text on
stderr, with exit code 2).

## JSON schema 

Every document has:

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | int | Always `1` for this schema. |
| `command` | string | `parse`, `check`, `run`, `trace` or `term`. |
| `ok` | bool | `true` if the command succeeded. |

Spans are objects `{"start_line", "start_column", "end_line", "end_column"}`
(lines and columns start at 1).

### parse
`ast`: the program as a tree. Every node has `type` (`Program`, `Assign`,
`Seq`, `If`, `While`, `Skip`, `Num`, `Var`, `Add`, `Sub`, `Mul`, `Eq`, `Gt`,
`Or`, `Not`), its fields and `span`.

### check
`file`: the checked file name.

### run
Success: `steps` (int), `final_state` (object variable -> int).
Runtime failure: `steps`, `state` (state at the moment of failure), `error`.

### trace
Always: `status` (`ok`, `error`, `step_limit`), `final_state`, `events`.
On failure also `error`. Each event has `type` and `step`:

### term
`style` (`course` or `ascii`), `text` (the term as text) and `term` (the term
as a tree of objects, for example `{"type": "WH", "cond": ..., "body": ...}`;
types: `Const`, `Deref`, `Basic`, `Super`, `AS`, `Comp`, `IF`, `WH`, `Id`).
With `--steps` there is also `steps`: a list of
`{"rule", "span", "term_text"}`, one for each rule `NS_*` that was applied.
See `docs/semantics.md` for the notation and the rules.

| `type` | Extra fields |
|--------|--------------|
| `program_started` | `state` |
| `before_statement` | `kind`, `span`, `state` |
| `after_statement` | `kind`, `span`, `state` |
| `variable_changed` | `name`, `old` (int or null), `new`, `span` |
| `condition_evaluated` | `kind` (`if`/`while`), `result`, `span` |
| `program_finished` | `status`, `state`, and for failures `error`, `error_span` |

`kind` of a statement is one of `assign`, `skip`, `if`, `while`.

### error object
`error` has `kind` (`syntax`, `runtime`, `step_limit`, `io`, `usage`) and
`message`. Syntax errors add `line`, `column`, `expected` (list of strings).
Runtime errors add `span`.

```json
{
  "schema_version": 1,
  "command": "check",
  "ok": false,
  "error": {
    "kind": "syntax",
    "message": "unexpected 'end'",
    "line": 1,
    "column": 12,
    "expected": ["'('", "number", "variable name"]
  }
}
```