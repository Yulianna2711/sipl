from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

CASES_DIR = Path(__file__).resolve().parent / "cases"
DEFAULT_CMD = os.environ.get("SIPL_CMD") or f'"{sys.executable}" -m sipl'

STATUS_MAP = {
    "syntax": "syntax_error",
    "runtime": "runtime_error",
    "step_limit": "step_limit",
}

def parse_args_for(kind: str, path: str, case: dict) -> list[str]:
    if kind == "ast":
        return ["parse", "--json", path]
    args = ["run", "--json", path]
    for name, value in case.get("initial_state", {}).items():
        args += ["--set", f"{name}={value}"]
    if "max_steps" in case:
        args += ["--max-steps", str(case["max_steps"])]
    return args

def normalize_run(proc: subprocess.CompletedProcess) -> dict:
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return {"status": "crash", "detail": (proc.stderr or proc.stdout)[-300:]}
    if proc.returncode == 0:
        return {"status": "ok", "state": data.get("final_state")}
    err = data.get("error") or {}
    line = err.get("line")
    if line is None:
        line = (err.get("span") or {}).get("start_line")
    return {
        "status": STATUS_MAP.get(err.get("kind", ""), "other_error"),
        "line": line,
    }

def to_sexpr(n) -> str:
    t = n["type"]
    if t == "Program":
        return f"(prog {to_sexpr(n['body'])})"
    if t == "Assign":
        return f"(assign {n['target']} {to_sexpr(n['expr'])})"
    if t == "Seq":
        stmts = [to_sexpr(s) for s in n["stmts"]]
        res = stmts[-1]
        for s in reversed(stmts[:-1]):
            res = f"(seq {s} {res})"
        return res
    if t == "If":
        return f"(if {to_sexpr(n['cond'])} {to_sexpr(n['then_branch'])} {to_sexpr(n['else_branch'])})"
    if t == "While":
        return f"(while {to_sexpr(n['cond'])} {to_sexpr(n['body'])})"
    if t == "Skip":
        return "(skip)"
    if t == "Add":
        return f"(+ {to_sexpr(n['left'])} {to_sexpr(n['right'])})"
    if t == "Sub":
        return f"(- {to_sexpr(n['left'])} {to_sexpr(n['right'])})"
    if t == "Mul":
        return f"(* {to_sexpr(n['left'])} {to_sexpr(n['right'])})"
    if t == "Eq":
        return f"(= {to_sexpr(n['left'])} {to_sexpr(n['right'])})"
    if t == "Gt":
        return f"(> {to_sexpr(n['left'])} {to_sexpr(n['right'])})"
    if t == "Or":
        return f"(or {to_sexpr(n['left'])} {to_sexpr(n['right'])})"
    if t == "Not":
        return f"(not {to_sexpr(n['operand'])})"
    if t == "Num":
        return str(n["value"])
    if t == "Var":
        return n["name"]
    raise ValueError(f"unknown AST node type: {t}")

def normalize_parse(proc: subprocess.CompletedProcess) -> dict:
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return {"status": "crash", "detail": (proc.stderr or proc.stdout)[-300:]}
    if proc.returncode != 0:
        return {"status": "error"}
    try:
        return {"status": "ok", "sexpr": to_sexpr(data["ast"])}
    except (KeyError, ValueError, TypeError) as exc:
        return {"status": "adapter_error", "detail": repr(exc)}

def load_cases() -> list[dict]:
    cases: list[dict] = []
    if not CASES_DIR.exists():
        return cases
    for f in sorted(CASES_DIR.glob("*.json")):
        for c in json.loads(f.read_text(encoding="utf-8")):
            c["_file"] = f.name
            cases.append(c)
    ids = [c["id"] for c in cases]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"duplicate case ids: {sorted(dup)}")
    return cases

def execute(base_cmd: str, case: dict) -> dict:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "prog.sipl"
        path.write_text(case["source"], encoding="utf-8")
        argv = shlex.split(base_cmd) + parse_args_for(case["kind"], str(path), case)
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}
    return normalize_parse(proc) if case["kind"] == "ast" else normalize_run(proc)


def check(case: dict, got: dict) -> list[str]:
    exp = case["expect"]
    problems: list[str] = []
    if case["kind"] == "ast":
        if got.get("status") != "ok":
            return [f"parse failed: {got}"]
        if got["sexpr"] != exp["sexpr"]:
            problems.append(f"AST mismatch:\n    expected {exp['sexpr']}\n    got      {got['sexpr']}")
        return problems
    if got.get("status") != exp["status"]:
        return [f"status: expected {exp['status']!r}, got {got.get('status')!r} ({got})"]
    if exp["status"] == "ok" and got.get("state") != exp["state"]:
        problems.append(f"state: expected {exp['state']}, got {got.get('state')}")
    if "line" in exp and got.get("line") != exp["line"]:
        problems.append(f"error line: expected {exp['line']}, got {got.get('line')}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="SIPL conformance runner")
    ap.add_argument("--cmd", default=DEFAULT_CMD, help='execution command, e.g. "python -m sipl"')
    ap.add_argument("--filter", default="", help="run only cases whose ID contains this string")
    args = ap.parse_args()

    cases = [c for c in load_cases() if args.filter in c["id"]]
    if not cases:
        print("No test cases found in 'cases/' directory.")
        return 0

    failed = 0
    for case in cases:
        problems = check(case, execute(args.cmd, case))
        if problems:
            failed += 1
            print(f"FAIL {case['id']}  ({case['_file']})")
            print(f"  {case['description']}")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"PASS {case['id']}")
    print(f"\n{len(cases) - failed}/{len(cases)} passed")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())