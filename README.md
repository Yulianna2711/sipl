# SIPL toolkit

## Selected tasks and claimed score

| ID | Task | Points |
|---|---|---|
| CORE-01 | Formal grammar (Lark) with positive and negative tests | 0.5 |
| CORE-02 | Parser and typed AST with source spans, syntax diagnostics | 1.5 |
| CORE-03 | Interpreter: state, assignment, if, while, begin/end, skip, step limit | 2.0 |
| CORE-04 | Event model and execution trace | 1.0 |
| CORE-05 | CLI parse/check/run/trace with JSON mode | 1.0 |
| CORE-06 | Conformance suite with documented format | 1.0 |
| SEM-01 | Semantic term construction in the course notation | 2.0 |
| SEM-02 | Evaluation of a term on a state with the trace of applied rules | 2.0 |
| | **Sum** | **11.0** |

## Installation

Requirements: Python 3.11 or newer and Git.

```
git clone https://github.com/Yulianna2711/sipl
cd sipl
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

The installation pulls `lark` (the parser library) and the development tools
(`pytest`, `pytest-cov`).

## Tests

```
python -m pytest
```

## Usage

```
python -m sipl check examples/power.sipl
python -m sipl run examples/power.sipl --set X=2 --set Y=5
python -m sipl trace examples/gcd.sipl --set M=12 --set N=18
python -m sipl term examples/power.sipl --steps
python -m sipl apply examples/power.sipl --set X=5 --set Y=2 --steps
```

A program can also be read from stdin: `echo "begin X := 1 end" | python -m sipl parse -`.
Every command accepts `--json` (structured output). `term` and `apply` accept
`--style ascii` for terminals without unicode.

Exit codes: 0 success, 1 syntax error, 2 usage or I/O error, 3 runtime error
(undefined variable, step limit, undefined term value).

## Examples

`examples/power.sipl`, `examples/gcd.sipl`, `examples/division.sipl`.

## Grammar

`grammar/sipl.lark`, version 1.0, based on the BNF of the course practicum. The
decisions that resolve its ambiguity (left associativity, operator precedence,
no `;` before `end`) are described in the header of the file and in `docs/grammar.md`.

## Documentation

- `docs/grammar.md`: the grammar and its design decisions
- `docs/cli.md`: commands, options, exit codes, JSON schema
- `docs/semantics.md`: semantic terms, construction rules and evaluation
- `docs/conformance.md`: format of the conformance suite

## Limitations

- Numbers in the source are unsigned integers; negative values come from `--set` or `0 - n`.
- `or` is strict (both operands are evaluated), as in the course term `S²(or, …)`.
- Termination is not decided: a loop is stopped after `--max-steps` steps and the
  result is reported as undefined.