# SIPL conformance suite

A test suite that checks an implementation of the SIPL language only through
the command line, without access to internal modules.

## Structure

```
conformance/
├── cases/              # data: JSON files with cases
│   ├── run.json
│   ├── ast.json
│   └── errors.json
└── run_conformance.py  # runner
tests/test_conformance.py  # connects the suite to pytest
docs/conformance.md        # this document
```

The cases do not depend on the implementation language. Everything that depends
on a particular CLI is gathered in one place, the `ADAPT` block.

## Case format

Each file in `conformance/cases/` is a JSON array of cases. Example of a `run` case:

```json
{
  "id": "power-from-task",
  "description": "R = X^Y from the task text",
  "kind": "run",
  "source": "begin\n  R := 1;\n  while Y > 0 do\n  begin\n    R := R * X;\n    Y := Y - 1\n  end\nend",
  "initial_state": {"X": 2, "Y": 10},
  "max_steps": 100000,
  "expect": {"status": "ok", "state": {"R": 1024, "X": 2, "Y": 0}}
}
```

Example of an `ast` case:

```json
{
  "id": "ast-precedence",
  "description": "* has higher precedence than +",
  "kind": "ast",
  "source": "begin\n  X := 1 + 2 * 3\nend",
  "expect": {"sexpr": "(prog (assign X (+ 1 (* 2 3))))"}
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | unique identifier (duplicates are rejected by the runner) |
| `description` | yes | what the case checks and why the expectation is what it is |
| `kind` | yes | `run` (execute the program) or `ast` (only parse it) |
| `source` | yes | text of the SIPL program |
| `initial_state` | no | initial state of the variables (for `run`), `{}` by default |
| `max_steps` | no | step limit of the execution (for `run`) |
| `expect` | yes | expected result, see below |

## Expected result (`expect`)

### kind = `run`

- `status` is one of:
  - `ok`: the program was parsed and executed to the end;
  - `syntax_error`: the text does not belong to the SIPL language (execution did not start);
  - `runtime_error`: an error during execution, for example a reference to a
    variable that is not in the state;
  - `step_limit`: the step limit was exceeded (protection against infinite loops).
- `state`: the complete final state (only for `ok`). This is a JSON object
  "variable name → integer". It is compared exactly, so there must be no extra
  or missing variables.
- `line`: (optional) the line number (from 1) the error must point to.

### kind = `ast`

- `sexpr`: the canonical form of the AST (below).

## Canonical form of the AST

The ASTs of different implementations look different (different classes,
different field names), so what is compared is not the AST itself but its
normalized S-expression:

| Construct | Form |
|---|---|
| program | `(prog S)` |
| assignment `x := a` | `(assign X E)` |
| sequence `S1; S2` | `(seq S1 S2)` |
| conditional | `(if B S1 S2)` |
| loop | `(while B S)` |
| empty statement | `(skip)` |
| arithmetic | `(+ a b)`, `(- a b)`, `(* a b)` |
| comparison | `(= a b)`, `(> a b)` |
| negation `¬b` | `(not b)` |
| disjunction `b1 ∨ b2` | `(or b1 b2)` |
| variable, number | `X`, `42` |

The block `begin S end` and the parentheses `(a)` do not appear in the form:
they are transparent (`sem_S(begin S end) = sem_S(S)`, `sem_A((a)) = sem_A(a)`).
Positions in the text (SourceSpan) are not compared.

An example with logical operators. Since `¬` has higher precedence than `∨`,
`¬ (X = 1) ∨ (X > 5)` is parsed as `(¬(X = 1)) ∨ (X > 5)`:

```
(prog (if (or (not (= X 1)) (> X 5)) (assign Y 1) (assign Y 0)))
```

## What exactly the suite fixes

- precedence and left associativity of operations: `10 - 2 - 3 = 5`;
- `;` has the lowest precedence, `while` and `if` bind tighter:
  `if b then S1 else S2; S3` is `(if ...); S3`;
- `begin ... end` is needed only for grouping; for a single statement in the
  body of a `while` or a branch of an `if` it is not used;
- partiality: an undefined variable gives `runtime_error`, an infinite loop gives `step_limit`;
- zero iterations of a loop leave the state unchanged;
- monotonicity: extra variables in the initial state remain in the result;
- conformance to the grammar: `;` before `end`, an empty block `begin end`, an
  extra `end` (case `syntax-stray-end`), a condition without a comparison, a
  missing `then` are syntax errors.

## CLI contract

The runner interacts with an implementation only through the following calls.
Let `<cmd>` be the command that starts the implementation (for example,
python -m sipl).

**Parsing**

```
<cmd> parse --json FILE
```

- exit code 0: stdout holds a JSON object with the key `ast` (the program tree);
- non-zero exit code: the program is syntactically incorrect.

**Execution**

```
<cmd> run --json FILE [--set NAME=VALUE]... [--max-steps N]
```

- `--set` gives the initial value of a variable, the flag can be repeated;
- `--max-steps` limits the number of steps;
- exit code 0: stdout holds a JSON object with the key `state` (the final state);
- non-zero exit code: stdout holds a JSON object with the key `error`:

```json
{"error": {"kind": "syntax", "line": 3, "message": "..."}}
```

where `kind` is one of `syntax`, `runtime`, `step_limit`, and `line` is the line
number from 1 (it can be `null` if the line is not determined).

The runner turns these responses into the statuses `ok` / `syntax_error` /
`runtime_error` / `step_limit`. If the process did not return valid JSON, the
status is `crash` (launching the implementation broke, as opposed to finding an
error in the program).

## Running

```
python conformance/run_conformance.py
python conformance/run_conformance.py --filter priority
python conformance/run_conformance.py --cmd "python -m sipl"
pytest tests/test_conformance.py -q
```

- `--cmd` is the command that starts the implementation. If it is not given,
  the environment variable `SIPL_CMD` is used, and if that is not set either,
  the current Python interpreter is used (`<sys.executable> -m sipl`). Thanks
  to this the suite works inside a virtual environment without extra setup.
- `--filter` runs only the cases whose id contains the given string.
- The exit code is 0 if all cases passed and 1 if there are failures.

For each failure the runner prints the case id, the file, the description and
the reason (the expected and the received value).

## Running against another implementation

To check another implementation of SIPL, adjust the `ADAPT` block in
`run_conformance.py`:

- `parse_args_for`: the names of the subcommands and flags (`--json`, `--set`, `--max-steps`);
- `normalize_run`: the keys of the JSON response (`state`, `error`, `kind`,
  `line`) and the mapping of `kind` values to statuses (`STATUS_MAP`);
- `to_sexpr`: the conversion of this implementation's JSON AST into the
  canonical S-expression.

The files in `conformance/cases/` do not need to be changed.